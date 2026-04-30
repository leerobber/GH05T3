"""GH05T3 — Memory Palace: SQLite-backed shard storage."""
from __future__ import annotations
import json
import os
import sqlite3
import time
from pathlib import Path

DB_PATH = Path(os.environ.get("MEMORY_DB_PATH", "memory/palace.db"))


class MemoryPalace:
    """Persistent memory store. Shards are text snippets tagged by room."""

    def __init__(self, db_path: Path = None):
        self._db = db_path or DB_PATH
        self._db.parent.mkdir(parents=True, exist_ok=True)
        self._shards: list[dict] = []
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db)

    def _init_db(self):
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS shards (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    room      TEXT    DEFAULT 'general',
                    content   TEXT    NOT NULL,
                    timestamp REAL    NOT NULL,
                    tags      TEXT    DEFAULT '[]'
                )
            """)
        self._load()

    def _load(self):
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, room, content, timestamp, tags FROM shards ORDER BY id"
            ).fetchall()
        self._shards = [
            {"id": r[0], "room": r[1], "content": r[2],
             "timestamp": r[3], "tags": json.loads(r[4] or "[]")}
            for r in rows
        ]

    def store(self, content: str, room: str = "general", tags: list = None) -> dict:
        now = time.time()
        tags_json = json.dumps(tags or [])
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO shards (room, content, timestamp, tags) VALUES (?,?,?,?)",
                (room, content, now, tags_json),
            )
            shard_id = cur.lastrowid
        shard = {"id": shard_id, "room": room, "content": content,
                  "timestamp": now, "tags": tags or []}
        self._shards.append(shard)
        return shard

    async def recall(self, query: str, room: str = None, top_k: int = 5) -> list[dict]:
        q = query.lower()
        hits = [
            s for s in self._shards
            if q in s["content"].lower() and (room is None or s["room"] == room)
        ]
        return sorted(hits, key=lambda x: x["timestamp"], reverse=True)[:top_k]

    def prune(self, max_shards: int = 5000) -> int:
        """Delete oldest shards so total stays at or below max_shards. Returns count removed."""
        total = len(self._shards)
        if total <= max_shards:
            return 0
        to_remove = total - max_shards
        oldest_ids = [s["id"] for s in self._shards[:to_remove]]
        with self._conn() as conn:
            conn.execute(
                f"DELETE FROM shards WHERE id IN ({','.join('?' * len(oldest_ids))})",
                oldest_ids,
            )
        self._shards = self._shards[to_remove:]
        return to_remove

    def stats(self) -> dict:
        rooms: dict[str, int] = {}
        for s in self._shards:
            rooms[s["room"]] = rooms.get(s["room"], 0) + 1
        return {
            "total_shards": len(self._shards),
            "rooms":        rooms,
            "db_path":      str(self._db),
        }
