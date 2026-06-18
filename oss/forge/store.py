"""SQLite store for curated training shards and agency run history."""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Iterator

from oss.forge.schemas import ForgeDomain, ForgeRunRecord, QualityTier, TrainingShard

_DB_PATH = Path(__file__).resolve().parents[2] / "backend" / "data" / "forge" / "forge.db"


def _conn() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


def _init() -> None:
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS shards (
                shard_id   TEXT PRIMARY KEY,
                domain     TEXT NOT NULL,
                tier       TEXT NOT NULL,
                score      REAL NOT NULL,
                content_hash TEXT NOT NULL UNIQUE,
                payload    TEXT NOT NULL,
                source     TEXT NOT NULL,
                genome_id  TEXT NOT NULL DEFAULT '',
                created_at REAL NOT NULL
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS shards_tier ON shards(tier)")
        c.execute("CREATE INDEX IF NOT EXISTS shards_domain ON shards(domain)")
        c.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                run_id     TEXT PRIMARY KEY,
                payload    TEXT NOT NULL,
                created_at REAL NOT NULL
            )
        """)


_init()


class ForgeStore:
    def save_shard(self, shard: TrainingShard, tier: QualityTier, score: float, content_hash: str) -> bool:
        with _conn() as c:
            try:
                c.execute(
                    """INSERT INTO shards (shard_id, domain, tier, score, content_hash, payload, source, genome_id, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        shard.shard_id,
                        shard.domain.value,
                        tier.value,
                        score,
                        content_hash,
                        json.dumps(shard.to_dict()),
                        shard.source,
                        shard.genome_id,
                        time.time(),
                    ),
                )
                return True
            except sqlite3.IntegrityError:
                return False

    def list_shards(
        self,
        min_tier: QualityTier = QualityTier.SILVER,
        domain: ForgeDomain | None = None,
        limit: int = 500,
    ) -> list[TrainingShard]:
        order = [t.value for t in QualityTier]
        min_idx = order.index(min_tier.value)
        allowed = set(order[min_idx:])
        q = "SELECT payload FROM shards WHERE tier IN ({})".format(
            ",".join("?" for _ in allowed)
        )
        params: list = list(allowed)
        if domain:
            q += " AND domain = ?"
            params.append(domain.value)
        q += " ORDER BY score DESC LIMIT ?"
        params.append(limit)
        with _conn() as c:
            rows = c.execute(q, params).fetchall()
        return [TrainingShard.from_dict(json.loads(r["payload"])) for r in rows]

    def stats(self) -> dict:
        with _conn() as c:
            total = c.execute("SELECT COUNT(*) FROM shards").fetchone()[0]
            by_tier = {
                r["tier"]: r["n"]
                for r in c.execute("SELECT tier, COUNT(*) n FROM shards GROUP BY tier").fetchall()
            }
            by_domain = {
                r["domain"]: r["n"]
                for r in c.execute("SELECT domain, COUNT(*) n FROM shards GROUP BY domain").fetchall()
            }
        return {"total": total, "by_tier": by_tier, "by_domain": by_domain}

    def save_run(self, record: ForgeRunRecord) -> None:
        with _conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO runs (run_id, payload, created_at) VALUES (?, ?, ?)",
                (record.run_id, json.dumps(record.to_dict()), time.time()),
            )

    def last_run(self) -> ForgeRunRecord | None:
        with _conn() as c:
            row = c.execute(
                "SELECT payload FROM runs ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
        if not row:
            return None
        data = json.loads(row["payload"])
        return ForgeRunRecord(**{k: data[k] for k in ForgeRunRecord.__dataclass_fields__})


_store: ForgeStore | None = None


def get_store() -> ForgeStore:
    global _store
    if _store is None:
        _store = ForgeStore()
    return _store