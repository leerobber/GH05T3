"""
Triage-and-Bid Memory Governance (MemArchitect-inspired)
=========================================================
Instead of an append-only memory log that creates "zombie memories"
(outdated, stale, or contradictory data clogging the context window),
this governor runs a periodic auction:

  1. Every stored fact must bid for its slot using a SCORE:
       score = (importance × confidence × recency_factor × utility)
       recency_factor = exp(-decay_rate × hours_since_access)

  2. Facts with score < EVICTION_THRESHOLD are archived to the Engram Vault
     (never deleted — just deprioritised and compressed).

  3. High-contradiction facts (belief conflicts) are flagged for
     reconsolidation by the Belief Hierarchy.

  4. A Triage Report is written to the Iron Dome chain after each run.

Schedule: runs automatically every 6 hours (can be triggered manually).

Usage:
    from memory.triage_governor import TriageGovernor
    gov = TriageGovernor()
    report = await gov.run_triage()
    print(report)
"""
from __future__ import annotations

import asyncio
import json
import logging
import math
import sqlite3
import time
from pathlib import Path
from typing import Dict, List, Optional

LOG = logging.getLogger("aethyro.triage_governor")

_DATA_DIR = Path(__file__).parent / "data"
_DB_PATH  = _DATA_DIR / "ghostrecall.db"

# Governance constants
EVICTION_THRESHOLD = 0.12   # below this score → evict to Engram Vault
DECAY_RATE         = 0.005  # exponential decay per hour since last access
MAX_CONTEXT_SLOTS  = 500    # max active memories in explicit layer
TRIAGE_INTERVAL_S  = 6 * 3600  # run every 6 hours


def _conn() -> sqlite3.Connection:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


# ─────────────────────────────────────────────────────────────────────────────
# Scoring
# ─────────────────────────────────────────────────────────────────────────────

def _triage_score(row: sqlite3.Row) -> float:
    """
    Compute the triage bid score for a memory record.
    Higher = more valuable = survives the auction.
    """
    now              = time.time()
    hours_idle       = (now - row["last_accessed"]) / 3600.0
    recency_factor   = math.exp(-DECAY_RATE * hours_idle)
    access_boost     = min(1.0, row["access_count"] / 10.0)  # more access → higher score
    score = (
        row["importance"]  * 0.35 +
        row["confidence"]  * 0.25 +
        row["utility"]     * 0.20 +
        recency_factor     * 0.15 +
        access_boost       * 0.05
    )
    return round(score, 4)


# ─────────────────────────────────────────────────────────────────────────────
# TriageGovernor
# ─────────────────────────────────────────────────────────────────────────────

class TriageGovernor:
    """
    Runs periodic memory triage auctions to prevent context contamination
    and zombie memory proliferation.
    """

    _instance: Optional["TriageGovernor"] = None

    def __init__(self):
        self._last_run: float = 0.0
        self._total_evicted: int = 0
        self._total_runs: int = 0

    @classmethod
    def instance(cls) -> "TriageGovernor":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def run_triage(self, force: bool = False) -> Dict:
        """
        Run the full triage cycle.
        Returns a report dict with stats.
        """
        from memory.iron_dome import dome_write
        from memory.ghostrecall import ghost

        now = time.time()
        if not force and (now - self._last_run) < TRIAGE_INTERVAL_S:
            remaining = TRIAGE_INTERVAL_S - (now - self._last_run)
            return {
                "skipped": True,
                "reason": f"Next triage in {remaining/3600:.1f}h",
                "last_run": self._last_run,
            }

        LOG.info("[TriageGovernor] Starting memory triage auction...")
        self._last_run = now
        self._total_runs += 1

        # ── Phase 1: Score all active explicit memories ─────────────────────
        with _conn() as c:
            rows = c.execute(
                "SELECT * FROM explicit_memory WHERE invalid_at IS NULL OR invalid_at > ?",
                (now,),
            ).fetchall()

        scored = [(row, _triage_score(row)) for row in rows]
        scored.sort(key=lambda x: x[1])  # lowest score first (evict candidates)

        evicted_ids: List[str] = []
        kept_count = 0
        total = len(scored)

        # ── Phase 2: Evict below threshold or overflow ───────────────────────
        overflow = max(0, total - MAX_CONTEXT_SLOTS)
        for i, (row, score) in enumerate(scored):
            should_evict = (score < EVICTION_THRESHOLD) or (i < overflow)
            if should_evict:
                evicted_ids.append(row["id"])
            else:
                kept_count += 1

        # ── Phase 3: Archive evicted memories to Engram Vault ───────────────
        archived_count = 0
        for mem_id in evicted_ids:
            try:
                await ghost.archive_to_engram(mem_id)
                archived_count += 1
            except Exception as e:
                LOG.warning("[TriageGovernor] Failed to archive %s: %s", mem_id[:8], e)

        self._total_evicted += archived_count

        # ── Phase 4: Detect belief contradictions ────────────────────────────
        contradictions = self._detect_contradictions()

        # ── Phase 5: Update utility scores based on access patterns ─────────
        await self._recompute_utility()

        # ── Phase 6: Build report + log to Iron Dome ─────────────────────────
        report = {
            "run_id": self._total_runs,
            "timestamp": now,
            "total_scored": total,
            "archived_to_engram": archived_count,
            "kept_active": kept_count,
            "contradictions_flagged": len(contradictions),
            "total_evicted_lifetime": self._total_evicted,
            "threshold": EVICTION_THRESHOLD,
            "overflow_evicted": overflow,
        }

        dome_write("TriageGovernor", "triage_complete", report)
        LOG.info(
            "[TriageGovernor] Triage complete: %d scored, %d archived, %d kept, %d contradictions",
            total, archived_count, kept_count, len(contradictions),
        )
        return report

    def _detect_contradictions(self) -> List[Dict]:
        """
        Simple contradiction detection: find beliefs with same type+agent
        but significantly different confidence values.
        """
        with _conn() as c:
            rows = c.execute(
                "SELECT agent_id, belief_type, COUNT(*) as cnt, "
                "MIN(confidence) as min_conf, MAX(confidence) as max_conf "
                "FROM belief_hierarchy "
                "GROUP BY agent_id, belief_type HAVING cnt > 1"
            ).fetchall()

        contradictions = []
        for row in rows:
            delta = row["max_conf"] - row["min_conf"]
            if delta > 0.4:
                contradictions.append({
                    "agent_id":    row["agent_id"],
                    "belief_type": row["belief_type"],
                    "count":       row["cnt"],
                    "confidence_delta": round(delta, 3),
                })
        return contradictions

    async def _recompute_utility(self) -> None:
        """
        Update utility scores based on recent access patterns.
        High-access memories get higher utility; stale ones get lower.
        """
        now = time.time()
        with _conn() as c:
            rows = c.execute(
                "SELECT id, access_count, created_at, last_accessed FROM explicit_memory "
                "WHERE invalid_at IS NULL OR invalid_at > ?",
                (now,),
            ).fetchall()
            for row in rows:
                days_alive = max(0.01, (now - row["created_at"]) / 86400.0)
                access_rate = row["access_count"] / days_alive
                # normalise: 10 accesses/day = utility 1.0
                utility = min(1.0, access_rate / 10.0)
                c.execute(
                    "UPDATE explicit_memory SET utility=? WHERE id=?",
                    (round(utility, 4), row["id"]),
                )

    def should_run(self) -> bool:
        """Return True if enough time has passed since last triage."""
        return (time.time() - self._last_run) >= TRIAGE_INTERVAL_S

    def stats(self) -> Dict:
        with _conn() as c:
            active = c.execute(
                "SELECT COUNT(*) FROM explicit_memory WHERE invalid_at IS NULL"
            ).fetchone()[0]
            engrams = c.execute("SELECT COUNT(*) FROM engram_vault").fetchone()[0]
        return {
            "active_memories":    active,
            "engram_vault":       engrams,
            "total_runs":         self._total_runs,
            "total_evicted":      self._total_evicted,
            "last_run":           self._last_run,
            "next_run_in_hours":  round(
                max(0, TRIAGE_INTERVAL_S - (time.time() - self._last_run)) / 3600, 2
            ),
            "eviction_threshold": EVICTION_THRESHOLD,
            "max_slots":          MAX_CONTEXT_SLOTS,
        }


# ── Singleton ─────────────────────────────────────────────────────────────────
governor = TriageGovernor.instance()


async def run_triage_loop() -> None:
    """Background loop that runs triage every TRIAGE_INTERVAL_S seconds."""
    LOG.info("[TriageGovernor] Background loop started (interval=%dh)", TRIAGE_INTERVAL_S // 3600)
    while True:
        if governor.should_run():
            try:
                report = await governor.run_triage()
                LOG.info("[TriageGovernor] Auto-triage: %s", report)
            except Exception as e:
                LOG.error("[TriageGovernor] Auto-triage error: %s", e)
        await asyncio.sleep(1800)  # check every 30 min
