from __future__ import annotations

import json
import logging
import sqlite3
import time
from pathlib import Path

from oss.dna.omni_dna import OmniDNA
from oss.schemas.genome import DNAType, Trait, GenomeRecord

LOG = logging.getLogger("oss.genome_store")

_ROOT = Path(__file__).resolve().parents[2]
_DB_PATH = _ROOT / "oss" / "data" / "genomes.db"

# Specialist trait seeds (registry slug → traits)
SEED_TRAITS: dict[str, dict[str, float]] = {
    "GH05T3": {"self_reflection": 0.85, "coding": 0.70, "creativity": 0.75},
    "ORACLE": {"research": 0.90, "math": 0.80, "self_reflection": 0.75},
    "FORGE": {"coding": 0.90, "creativity": 0.70, "math": 0.65},
    "CODEX": {"coding": 0.85, "math": 0.75, "self_reflection": 0.70},
    "SENTINEL": {"security": 0.90, "self_reflection": 0.80, "research": 0.70},
    "NEXUS": {"ops": 0.90, "coding": 0.60, "self_reflection": 0.65},
}

SEED_NAMES: dict[str, str] = {
    "GH05T3": "Avery",
    "ORACLE": "Iris Chen",
    "FORGE": "Marcus Reid",
    "CODEX": "Zoe Nakamura",
    "SENTINEL": "Viktor Steele",
    "NEXUS": "Kai Okafor",
}

_store: GenomeStore | None = None


class GenomeStore:
    def __init__(self, db_path: Path = _DB_PATH) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(str(self.db_path), check_same_thread=False)
        c.row_factory = sqlite3.Row
        return c

    def _init_db(self) -> None:
        with self._conn() as c:
            c.execute("""
                CREATE TABLE IF NOT EXISTS genomes (
                    genome_id TEXT PRIMARY KEY,
                    registry_agent_id TEXT NOT NULL,
                    display_name TEXT,
                    generation INTEGER DEFAULT 0,
                    parent_id TEXT,
                    payload TEXT NOT NULL,
                    updated_at REAL
                )
            """)
            c.execute("""
                CREATE INDEX IF NOT EXISTS idx_genomes_registry
                ON genomes(registry_agent_id)
            """)

    def save(self, dna: OmniDNA) -> GenomeRecord:
        record = dna.to_record()
        record.genome_id = dna.genome_id or dna.unique_id
        payload = json.dumps(record.to_dict(), ensure_ascii=False)
        with self._conn() as c:
            c.execute(
                """
                INSERT INTO genomes (genome_id, registry_agent_id, display_name,
                                     generation, parent_id, payload, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(genome_id) DO UPDATE SET
                    payload=excluded.payload,
                    generation=excluded.generation,
                    parent_id=excluded.parent_id,
                    updated_at=excluded.updated_at
                """,
                (
                    record.genome_id,
                    record.registry_agent_id,
                    record.display_name,
                    record.generation,
                    record.parent_id,
                    payload,
                    time.time(),
                ),
            )
        return record

    def get(self, genome_id: str) -> OmniDNA | None:
        with self._conn() as c:
            row = c.execute(
                "SELECT payload FROM genomes WHERE genome_id = ?", (genome_id,)
            ).fetchone()
        if not row:
            return None
        return OmniDNA.from_record(self._payload_to_record(json.loads(row["payload"])))

    def get_by_registry(self, registry_agent_id: str) -> OmniDNA | None:
        with self._conn() as c:
            row = c.execute(
                """
                SELECT payload FROM genomes
                WHERE registry_agent_id = ?
                ORDER BY updated_at DESC LIMIT 1
                """,
                (registry_agent_id.upper(),),
            ).fetchone()
        if not row:
            return None
        return OmniDNA.from_record(self._payload_to_record(json.loads(row["payload"])))

    def list_all(self) -> list[GenomeRecord]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT payload FROM genomes ORDER BY registry_agent_id"
            ).fetchall()
        return [self._payload_to_record(json.loads(r["payload"])) for r in rows]

    def _payload_to_record(self, data: dict) -> GenomeRecord:
        traits = {
            k: Trait.from_dict(v) if isinstance(v, dict) else Trait(k, float(v))
            for k, v in data.get("traits", {}).items()
        }
        qt_raw = data.get("quantum_traits") or {}
        qt: dict[str, list[tuple[float, float]]] = {}
        for name, pairs in qt_raw.items():
            if pairs and isinstance(pairs[0], dict):
                qt[name] = [(float(p["value"]), float(p["weight"])) for p in pairs]
            else:
                qt[name] = [(float(v), float(w)) for v, w in pairs]
        return GenomeRecord(
            genome_id=data["genome_id"],
            registry_agent_id=data["registry_agent_id"],
            display_name=data.get("display_name", ""),
            traits=traits,
            dna_type=DNAType[data.get("dna_type", "OMEGA")],
            qualia=data.get("qualia") or {},
            phenomenal_memory=data.get("phenomenal_memory") or [],
            evolution_history=data.get("evolution_history") or [],
            parent_id=data.get("parent_id"),
            generation=int(data.get("generation", 0)),
            quantum_traits=qt,
        )

    def seed_specialists(self) -> list[GenomeRecord]:
        saved: list[GenomeRecord] = []
        for slug, trait_map in SEED_TRAITS.items():
            if self.get_by_registry(slug):
                continue
            dna = OmniDNA(
                registry_agent_id=slug,
                display_name=SEED_NAMES.get(slug, slug),
                traits={
                    name: Trait(name, val, DNAType.GENETIC)
                    for name, val in trait_map.items()
                },
            )
            dna.genome_id = dna.unique_id
            saved.append(self.save(dna))
            LOG.info("Seeded genome %s (%s)", dna.genome_id, slug)

        try:
            from oss.adapters.registry import sync_specialists_only
            sync_specialists_only(self)
        except Exception as exc:
            LOG.warning("Registry specialist sync failed: %s", exc)

        return saved


def get_store() -> GenomeStore:
    global _store
    if _store is None:
        _store = GenomeStore()
    return _store