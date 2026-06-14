"""GH05T3 — Local Economy Ledger (SQLite-backed, SovereignCore-independent).

Self-contained credit accounting that works whether or not the external
SovereignCore service at :8081 is online.  economy_bridge.py posts to
SovereignCore first but ALWAYS records transactions here locally, so the
economy never goes dark.

Tables live in palace.db alongside memory shards and entropy drift logs:

    agent_credits       — current running balance per agent (upsert-based)
    credit_transactions — immutable append-only ledger (audit trail)

Env vars:
    ECONOMY_DB_PATH   override for the SQLite file (default: memory/palace.db)
    ECONOMY_LOG_LEVEL "verbose" to log every transaction (default: summary only)
"""
from __future__ import annotations

import logging
import math
import os
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

LOG = logging.getLogger("ghost.economy.ledger")

_DB_PATH = Path(os.environ.get("ECONOMY_DB_PATH",
                               str(Path(__file__).parent.parent / "memory" / "palace.db")))
_VERBOSE = os.environ.get("ECONOMY_LOG_LEVEL", "").lower() == "verbose"

# Agents that exist in the economy — used for balance initialisation
KNOWN_AGENTS = {
    "GH05T3-Avery", "ORACLE", "FORGE", "CODEX", "SENTINEL",
    "NEXUS", "LEDGER", "CHRONICLE", "KAIROS",
}


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

@contextmanager
def _conn(immediate: bool = False):
    """Open a WAL-mode connection with explicit transaction management.

    Use immediate=True for read-modify-write ops to prevent concurrent
    writes from interleaving between the SELECT and the INSERT/UPDATE.
    """
    c = sqlite3.connect(_DB_PATH, timeout=10, check_same_thread=False,
                        isolation_level=None)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
    try:
        yield c
        c.execute("COMMIT")
    except Exception:
        try:
            c.execute("ROLLBACK")
        except Exception:
            pass
        raise
    finally:
        c.close()


def _init_db():
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS agent_credits (
                agent_id  TEXT PRIMARY KEY,
                balance   REAL NOT NULL DEFAULT 0,
                updated   REAL NOT NULL DEFAULT 0
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS credit_transactions (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                ts        REAL    NOT NULL,
                agent_id  TEXT    NOT NULL,
                delta     REAL    NOT NULL,
                balance   REAL    NOT NULL,
                reason    TEXT    NOT NULL DEFAULT '',
                source    TEXT    NOT NULL DEFAULT 'local'
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_tx_agent ON credit_transactions(agent_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_tx_ts    ON credit_transactions(ts)")
        # Seed zero balances for all known agents on first boot
        for aid in KNOWN_AGENTS:
            c.execute(
                "INSERT OR IGNORE INTO agent_credits (agent_id, balance, updated) VALUES (?,0,?)",
                (aid, time.time()),
            )


# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------

@dataclass
class TxRecord:
    id:       int
    ts:       float
    agent_id: str
    delta:    float
    balance:  float
    reason:   str
    source:   str


# ---------------------------------------------------------------------------
# Core Ledger class
# ---------------------------------------------------------------------------

class Ledger:
    """Thread-safe, process-safe SQLite credit ledger."""

    def __init__(self):
        _init_db()

    # ── write ops ────────────────────────────────────────────────────────────

    def credit(self, agent_id: str, amount: float, reason: str = "",
               source: str = "local") -> float:
        """Add credits. Returns new balance."""
        if not math.isfinite(amount) or amount <= 0:
            raise ValueError(f"Credit amount must be a positive finite number, got {amount}")
        return self._apply(agent_id, +amount, reason, source)

    def debit(self, agent_id: str, amount: float, reason: str = "",
              source: str = "local") -> float:
        """Subtract credits (will go negative — enforce limits at call site).
        Returns new balance."""
        if not math.isfinite(amount) or amount <= 0:
            raise ValueError(f"Debit amount must be a positive finite number, got {amount}")
        return self._apply(agent_id, -amount, reason, source)

    def _apply(self, agent_id: str, delta: float, reason: str, source: str) -> float:
        with _conn(immediate=True) as c:
            row = c.execute(
                "SELECT balance FROM agent_credits WHERE agent_id=?", (agent_id,)
            ).fetchone()
            old_bal = row[0] if row else 0.0
            new_bal = old_bal + delta
            c.execute(
                "INSERT OR REPLACE INTO agent_credits (agent_id, balance, updated) VALUES (?,?,?)",
                (agent_id, new_bal, time.time()),
            )
            c.execute(
                "INSERT INTO credit_transactions (ts, agent_id, delta, balance, reason, source) "
                "VALUES (?,?,?,?,?,?)",
                (time.time(), agent_id, delta, new_bal, reason[:200], source),
            )
        sign = "+" if delta >= 0 else ""
        if _VERBOSE:
            LOG.info("[ledger] %s  %s%.1f cr  → %.1f  (%s)", agent_id, sign, delta, new_bal, reason[:60])
        return new_bal

    # ── read ops ─────────────────────────────────────────────────────────────

    def balance(self, agent_id: str) -> float:
        with _conn() as c:
            row = c.execute(
                "SELECT balance FROM agent_credits WHERE agent_id=?", (agent_id,)
            ).fetchone()
        return row[0] if row else 0.0

    def all_balances(self) -> dict[str, float]:
        with _conn() as c:
            rows = c.execute(
                "SELECT agent_id, balance FROM agent_credits ORDER BY balance DESC"
            ).fetchall()
        return {r[0]: r[1] for r in rows}

    def history(self, agent_id: str, limit: int = 50) -> list[TxRecord]:
        with _conn() as c:
            rows = c.execute(
                "SELECT id, ts, agent_id, delta, balance, reason, source "
                "FROM credit_transactions WHERE agent_id=? "
                "ORDER BY ts DESC LIMIT ?",
                (agent_id, limit),
            ).fetchall()
        return [TxRecord(*r) for r in rows]

    def stats(self) -> dict:
        with _conn() as c:
            total_tx = c.execute("SELECT COUNT(*) FROM credit_transactions").fetchone()[0]
            total_issued = c.execute(
                "SELECT COALESCE(SUM(delta),0) FROM credit_transactions WHERE delta>0"
            ).fetchone()[0]
            total_spent = c.execute(
                "SELECT COALESCE(SUM(delta),0) FROM credit_transactions WHERE delta<0"
            ).fetchone()[0]
            rich = c.execute(
                "SELECT agent_id, balance FROM agent_credits ORDER BY balance DESC LIMIT 1"
            ).fetchone()
        return {
            "total_transactions": total_tx,
            "total_issued":       round(total_issued, 2),
            "total_spent":        round(abs(total_spent), 2),
            "circulating":        round(total_issued + total_spent, 2),
            "richest_agent":      rich[0] if rich else None,
            "richest_balance":    round(rich[1], 2) if rich else 0,
            "all_balances":       self.all_balances(),
        }


# ---------------------------------------------------------------------------
# Module-level singleton + convenience functions
# ---------------------------------------------------------------------------

_ledger: Optional[Ledger] = None


def get_ledger() -> Ledger:
    global _ledger
    if _ledger is None:
        _ledger = Ledger()
    return _ledger


def credit(agent_id: str, amount: float, reason: str = "", source: str = "local") -> float:
    return get_ledger().credit(agent_id, amount, reason, source)


def debit(agent_id: str, amount: float, reason: str = "", source: str = "local") -> float:
    return get_ledger().debit(agent_id, amount, reason, source)


def balance(agent_id: str) -> float:
    return get_ledger().balance(agent_id)


def ledger_stats() -> dict:
    return get_ledger().stats()
