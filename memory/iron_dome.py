"""
Iron Dome — SHA-256 Hash Chain Ledger
======================================
Every write to the system state is chained: each record contains the SHA-256
of the previous record's hash, making it mathematically impossible to tamper
with previous state without immediately invalidating the chain.

Design:
  - Append-only SQLite table with chain verification
  - Supports: memory writes, system mutations, agent actions, SAGE proposals
  - Chain break detection on read
  - Export / audit API

Usage:
    from memory.iron_dome import IronDome
    dome = IronDome()
    rec_id = dome.write("SAGE", "proposal_deployed", {"proposal_id": "p-001", "score": 0.92})
    is_valid = dome.verify_chain()
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

LOG = logging.getLogger("aethyro.iron_dome")

_DATA_DIR = Path(__file__).parent / "data"
_DB_PATH  = _DATA_DIR / "iron_dome.db"

GENESIS_HASH = "0" * 64  # Genesis block — no previous hash

# Serialise all writes so seq/prev_hash reads and INSERT are one atomic unit.
# Without this lock, two concurrent dome_write() calls can read the same seq
# and both insert records with identical seq values, silently corrupting the
# hash chain.  threading.Lock works across asyncio tasks on the same thread.
_write_lock = threading.Lock()


# ─────────────────────────────────────────────────────────────────────────────
# DB bootstrap
# ─────────────────────────────────────────────────────────────────────────────

def _conn() -> sqlite3.Connection:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


def _init_db() -> None:
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS chain_ledger (
                id          TEXT PRIMARY KEY,
                seq         INTEGER NOT NULL,
                actor       TEXT NOT NULL,
                event_type  TEXT NOT NULL,
                payload     TEXT NOT NULL DEFAULT '{}',
                prev_hash   TEXT NOT NULL,
                record_hash TEXT NOT NULL,
                created_at  REAL NOT NULL
            )
        """)
        c.execute(
            "CREATE INDEX IF NOT EXISTS chain_seq ON chain_ledger(seq)"
        )
        c.execute(
            "CREATE INDEX IF NOT EXISTS chain_actor ON chain_ledger(actor)"
        )
        c.execute(
            "CREATE INDEX IF NOT EXISTS chain_event ON chain_ledger(event_type)"
        )
        LOG.debug("Iron Dome ledger initialised at %s", _DB_PATH)


_init_db()


# ─────────────────────────────────────────────────────────────────────────────
# Hash helpers
# ─────────────────────────────────────────────────────────────────────────────

def _sha256(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _compute_hash(seq: int, actor: str, event_type: str,
                  payload: str, prev_hash: str, created_at: float) -> str:
    raw = f"{seq}|{actor}|{event_type}|{payload}|{prev_hash}|{created_at}"
    return _sha256(raw)


# ─────────────────────────────────────────────────────────────────────────────
# IronDome class
# ─────────────────────────────────────────────────────────────────────────────

class IronDome:
    """Append-only SHA-256 Hash Chain Ledger for system state integrity."""

    _instance: Optional["IronDome"] = None

    def __init__(self):
        self._conn = _conn

    @classmethod
    def instance(cls) -> "IronDome":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ── Internal ──────────────────────────────────────────────────────────────

    def _last_record(self) -> Optional[sqlite3.Row]:
        """Return the most recent chain record (used by verify_chain / stats)."""
        with self._conn() as c:
            row = c.execute(
                "SELECT * FROM chain_ledger ORDER BY seq DESC LIMIT 1"
            ).fetchone()
        return row

    # ── Public API ────────────────────────────────────────────────────────────

    def write(
        self,
        actor: str,
        event_type: str,
        payload: Dict[str, Any] | None = None,
    ) -> str:
        """
        Append a record to the chain. Returns the new record's ID.

        THREAD SAFETY: _write_lock serialises the SELECT-seq / compute-hash /
        INSERT sequence so concurrent callers cannot produce duplicate seq values
        or break the prev_hash linkage.

        Args:
            actor:      Who generated this event (e.g. "SAGE", "FORGE", "NEXUS")
            event_type: Category string (e.g. "proposal_deployed", "memory_write")
            payload:    Arbitrary JSON-serialisable dict

        Returns:
            record_id (str)
        """
        payload_str = json.dumps(payload or {}, sort_keys=True)
        created_at  = time.time()
        rec_id      = str(uuid.uuid4())

        with _write_lock:  # atomic: read-last / compute-hash / insert
            with self._conn() as c:
                last = c.execute(
                    "SELECT seq, record_hash FROM chain_ledger ORDER BY seq DESC LIMIT 1"
                ).fetchone()
                seq       = (last["seq"] + 1)         if last else 1
                prev_hash = last["record_hash"]        if last else GENESIS_HASH
                record_hash = _compute_hash(
                    seq, actor, event_type, payload_str, prev_hash, created_at
                )
                c.execute(
                    """
                    INSERT INTO chain_ledger
                        (id, seq, actor, event_type, payload, prev_hash, record_hash, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (rec_id, seq, actor, event_type, payload_str,
                     prev_hash, record_hash, created_at),
                )

        LOG.debug(
            "[IronDome] #%d  %s/%s  hash=%.12s...", seq, actor, event_type, record_hash
        )
        return rec_id

    def verify_chain(self) -> Tuple[bool, List[str]]:
        """
        Walk the entire chain and verify hash linkage.

        Returns:
            (is_valid: bool, errors: List[str])
        """
        errors: List[str] = []
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM chain_ledger ORDER BY seq ASC"
            ).fetchall()

        prev_hash = GENESIS_HASH
        for row in rows:
            expected = _compute_hash(
                row["seq"], row["actor"], row["event_type"],
                row["payload"], row["prev_hash"], row["created_at"],
            )
            if row["record_hash"] != expected:
                errors.append(
                    f"HASH MISMATCH at seq={row['seq']} id={row['id']}: "
                    f"expected {expected[:16]}… got {row['record_hash'][:16]}…"
                )
            if row["prev_hash"] != prev_hash:
                errors.append(
                    f"CHAIN BREAK at seq={row['seq']} id={row['id']}: "
                    f"expected prev={prev_hash[:16]}… got {row['prev_hash'][:16]}…"
                )
            prev_hash = row["record_hash"]

        if errors:
            LOG.error("[IronDome] Chain verification FAILED: %d errors", len(errors))
        else:
            LOG.info("[IronDome] Chain verified OK — %d records", len(rows))
        return not bool(errors), errors

    def recent(self, n: int = 50, actor: str | None = None,
               event_type: str | None = None) -> List[Dict]:
        """Return the N most recent records, optionally filtered."""
        with self._conn() as c:
            if actor and event_type:
                rows = c.execute(
                    "SELECT * FROM chain_ledger WHERE actor=? AND event_type=? "
                    "ORDER BY seq DESC LIMIT ?",
                    (actor, event_type, n),
                ).fetchall()
            elif actor:
                rows = c.execute(
                    "SELECT * FROM chain_ledger WHERE actor=? "
                    "ORDER BY seq DESC LIMIT ?",
                    (actor, n),
                ).fetchall()
            elif event_type:
                rows = c.execute(
                    "SELECT * FROM chain_ledger WHERE event_type=? "
                    "ORDER BY seq DESC LIMIT ?",
                    (event_type, n),
                ).fetchall()
            else:
                rows = c.execute(
                    "SELECT * FROM chain_ledger ORDER BY seq DESC LIMIT ?",
                    (n,),
                ).fetchall()
        return [
            {
                "id": r["id"],
                "seq": r["seq"],
                "actor": r["actor"],
                "event_type": r["event_type"],
                "payload": json.loads(r["payload"]),
                "hash": r["record_hash"][:16] + "…",
                "created_at": r["created_at"],
            }
            for r in rows
        ]

    def stats(self) -> Dict:
        with self._conn() as c:
            total = c.execute("SELECT COUNT(*) FROM chain_ledger").fetchone()[0]
            actors = c.execute(
                "SELECT actor, COUNT(*) as cnt FROM chain_ledger GROUP BY actor"
            ).fetchall()
            events = c.execute(
                "SELECT event_type, COUNT(*) as cnt FROM chain_ledger GROUP BY event_type"
            ).fetchall()
        return {
            "total_records": total,
            "by_actor": {r["actor"]: r["cnt"] for r in actors},
            "by_event": {r["event_type"]: r["cnt"] for r in events},
            "chain_valid": self.verify_chain()[0],
        }


# ── Singleton shortcut ─────────────────────────────────────────────────────────
_dome = IronDome.instance()


def dome_write(actor: str, event_type: str,
               payload: Dict | None = None) -> str:
    """Module-level shortcut for IronDome.write() — sync, thread-safe."""
    return _dome.write(actor, event_type, payload)


async def dome_write_async(actor: str, event_type: str,
                           payload: Dict | None = None) -> str:
    """
    Async-safe wrapper for dome_write.
    Use this inside async functions to avoid blocking the event loop —
    SQLite I/O can take 5-20ms and will stall all coroutines if called
    directly from an async context.
    """
    return await asyncio.to_thread(dome_write, actor, event_type, payload)


def dome_verify() -> Tuple[bool, List[str]]:
    """Module-level shortcut for IronDome.verify_chain()."""
    return _dome.verify_chain()
