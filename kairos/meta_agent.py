"""
Meta-Agent — Rewrites Improvement Rules Every 3 SAGE Cycles
============================================================
The Meta-Agent is the final stage of the SAGE evolutionary loop:
  Proposer → Critic → Verifier → Meta-Agent

Every 3 SAGE cycles, it:
  1. Analyses the outcomes of the previous cycles (what passed? what failed?)
  2. Identifies patterns in what makes proposals succeed or fail
  3. Rewrites the KAIROS improvement rules to encode these patterns
  4. Increments the rules version and logs the change to Iron Dome
  5. Signals the KAIROSEngine to reload its rules

This is the "learn how to learn" component — the OS improves its
own improvement mechanism over time.

Usage:
    meta = MetaAgent()
    await meta.maybe_rewrite(cycle_number=3, cycle_reports=[...])
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

LOG = logging.getLogger("aethyro.meta_agent")

_OLLAMA_URL  = "http://localhost:11434/api/generate"
_META_MODEL  = "avery-sovereign"
_RULES_PATH  = Path(__file__).parent / "data" / "improvement_rules.json"
_HISTORY_PATH = Path(__file__).parent / "data" / "meta_agent_history.jsonl"

META_REWRITE_EVERY = 3  # rewrite rules every N SAGE cycles


# ─────────────────────────────────────────────────────────────────────────────
# MetaAgent
# ─────────────────────────────────────────────────────────────────────────────

class MetaAgent:
    """
    Analyses SAGE cycle outcomes and rewrites KAIROS improvement rules
    every META_REWRITE_EVERY cycles.
    """

    _instance: Optional["MetaAgent"] = None

    def __init__(self):
        self._rewrites = 0
        self._last_rewrite_cycle: int = 0

    @classmethod
    def instance(cls) -> "MetaAgent":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _load_rules(self) -> Dict:
        if _RULES_PATH.exists():
            try:
                return json.loads(_RULES_PATH.read_text())
            except Exception:
                pass
        return {"version": 1, "meta_cycles": 0, "rules": [], "updated_at": time.time()}

    def _save_rules(self, rules: Dict) -> None:
        _RULES_PATH.parent.mkdir(parents=True, exist_ok=True)
        _RULES_PATH.write_text(json.dumps(rules, indent=2))

    def _log_history(self, record: Dict) -> None:
        _HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_HISTORY_PATH, "a") as f:
            f.write(json.dumps(record) + "\n")

    async def _analyse_cycles(self, cycle_reports: List[Dict]) -> str:
        """Ask the LLM to analyse cycle reports and identify patterns."""
        if not cycle_reports:
            return "No cycle data available."

        # Build a compact summary of each cycle
        summaries = []
        for i, report in enumerate(cycle_reports):
            summaries.append(
                f"Cycle {i+1}: "
                f"proposals={report.get('proposals_generated', 0)}, "
                f"passed={report.get('proposals_passed', 0)}, "
                f"deployed={report.get('proposals_deployed', 0)}, "
                f"avg_score={report.get('avg_score', 0):.2f}, "
                f"common_failures={report.get('common_failures', [])}"
            )

        prompt = f"""You are the Meta-Agent of the Aethyro SAGE self-improvement system.
You have access to the last {len(cycle_reports)} SAGE cycle reports.

## Cycle Reports
{chr(10).join(summaries)}

## Current Improvement Rules
{json.dumps(self._load_rules().get('rules', []), indent=2)[:2000]}

Analyse these cycles and identify:
1. What types of proposals consistently pass verification?
2. What types consistently fail? What are the root causes?
3. Which current rules are working well? Which are too strict or too lenient?
4. What 2-3 NEW rules would improve pass rates without compromising safety?
5. Which existing rules should be updated or removed?

Format each proposed change as:
RULE_ADD: <phase> | <directive>
RULE_UPDATE: <rule_id> | <new_directive>
RULE_REMOVE: <rule_id> | <reason>
INSIGHT: <key learning from this cycle batch>

Be specific. Focus on what actually changes agent behaviour."""

        async def _do_call() -> str:
            async with httpx.AsyncClient(timeout=httpx.Timeout(90.0, connect=10.0)) as client:
                r = await client.post(_OLLAMA_URL, json={
                    "model": _META_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.2, "num_predict": 768},
                })
                if r.status_code == 200:
                    return r.json().get("response", "").strip()
            return ""

        try:
            return await asyncio.wait_for(_do_call(), timeout=105.0)
        except asyncio.TimeoutError:
            LOG.warning("[MetaAgent] LLM analysis timed out (105s)")
            return ""
        except Exception as e:
            LOG.warning("[MetaAgent] LLM analysis failed: %s", e)
            return ""

    def _parse_rule_changes(self, analysis: str, current_rules: Dict) -> Dict:
        """Parse LLM output into concrete rule changes."""
        rules = list(current_rules.get("rules", []))
        insights = []

        for line in analysis.splitlines():
            stripped = line.strip()

            if stripped.startswith("RULE_ADD:"):
                # RULE_ADD: Implement | Always check for existing implementations before creating new ones
                parts = stripped[9:].split("|", 1)
                if len(parts) == 2:
                    phase, directive = parts[0].strip(), parts[1].strip()
                    new_id = f"R{len(rules)+1:03d}"
                    rules.append({
                        "id": new_id,
                        "phase": phase,
                        "directive": directive,
                        "weight": 0.85,
                        "added_by": "meta_agent",
                        "added_at": time.time(),
                    })
                    LOG.info("[MetaAgent] Added rule %s: %s", new_id, directive[:60])

            elif stripped.startswith("RULE_UPDATE:"):
                # RULE_UPDATE: R003 | Updated directive text
                parts = stripped[12:].split("|", 1)
                if len(parts) == 2:
                    rule_id, new_directive = parts[0].strip(), parts[1].strip()
                    for r in rules:
                        if r["id"] == rule_id:
                            r["directive"] = new_directive
                            r["updated_at"] = time.time()
                            LOG.info("[MetaAgent] Updated rule %s", rule_id)

            elif stripped.startswith("RULE_REMOVE:"):
                # RULE_REMOVE: R002 | No longer relevant
                parts = stripped[12:].split("|", 1)
                if parts:
                    rule_id = parts[0].strip()
                    rules = [r for r in rules if r["id"] != rule_id]
                    LOG.info("[MetaAgent] Removed rule %s", rule_id)

            elif stripped.startswith("INSIGHT:"):
                insights.append(stripped[8:].strip())

        new_rules = dict(current_rules)
        new_rules["rules"]       = rules
        new_rules["meta_cycles"] = current_rules.get("meta_cycles", 0) + 1
        new_rules["version"]     = current_rules.get("version", 1) + 1
        new_rules["updated_at"]  = time.time()
        new_rules["last_insights"] = insights
        return new_rules

    async def maybe_rewrite(
        self,
        cycle_number: int,
        cycle_reports: List[Dict],
    ) -> Optional[Dict]:
        """
        Check if it's time to rewrite improvement rules.
        Called after each SAGE cycle completes.

        Args:
            cycle_number:   The current SAGE cycle number (1-indexed)
            cycle_reports:  List of reports from recent cycles

        Returns:
            New rules dict if rewrite occurred, None otherwise.
        """
        if cycle_number % META_REWRITE_EVERY != 0:
            return None

        if cycle_number == self._last_rewrite_cycle:
            return None

        LOG.info(
            "[MetaAgent] Cycle %d triggers meta-rewrite (every %d cycles)",
            cycle_number, META_REWRITE_EVERY,
        )

        self._last_rewrite_cycle = cycle_number
        self._rewrites += 1

        # Get relevant cycle reports (last META_REWRITE_EVERY cycles)
        relevant_reports = cycle_reports[-META_REWRITE_EVERY:]

        # Analyse and generate rule changes
        analysis = await self._analyse_cycles(relevant_reports)

        # Parse and apply changes
        current_rules = self._load_rules()
        new_rules     = self._parse_rule_changes(analysis, current_rules)

        # Save to disk
        self._save_rules(new_rules)

        # Log to Iron Dome (async wrapper avoids blocking the event loop)
        try:
            from memory.iron_dome import dome_write_async
            await dome_write_async("MetaAgent", "rules_rewritten", {
                "meta_rewrite_number": self._rewrites,
                "cycle_number":        cycle_number,
                "new_version":         new_rules["version"],
                "rules_count":         len(new_rules.get("rules", [])),
                "insights_count":      len(new_rules.get("last_insights", [])),
            })
        except Exception:
            pass

        # Log to history
        self._log_history({
            "rewrite_id":     str(uuid.uuid4())[:8],
            "cycle_number":   cycle_number,
            "meta_rewrite_n": self._rewrites,
            "new_version":    new_rules["version"],
            "analysis":       analysis[:500],
            "rules_count":    len(new_rules.get("rules", [])),
            "insights":       new_rules.get("last_insights", []),
            "ts":             time.time(),
        })

        LOG.info(
            "[MetaAgent] Rules rewritten → version=%d rules=%d insights=%d",
            new_rules["version"],
            len(new_rules.get("rules", [])),
            len(new_rules.get("last_insights", [])),
        )
        return new_rules

    def history(self, limit: int = 20) -> List[Dict]:
        """Return the last N meta-agent rewrite records."""
        if not _HISTORY_PATH.exists():
            return []
        lines = _HISTORY_PATH.read_text().strip().splitlines()
        results = []
        for line in reversed(lines[-limit:]):
            try:
                results.append(json.loads(line))
            except Exception:
                pass
        return results

    def stats(self) -> Dict:
        rules = self._load_rules()
        return {
            "total_rewrites":      self._rewrites,
            "rewrite_every":       META_REWRITE_EVERY,
            "current_rules_count": len(rules.get("rules", [])),
            "rules_version":       rules.get("version", 1),
            "meta_cycles":         rules.get("meta_cycles", 0),
            "last_rewrite_cycle":  self._last_rewrite_cycle,
        }
