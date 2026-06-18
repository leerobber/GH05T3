"""AgencyForge — autonomous curation cycle with genome-aware feel."""
from __future__ import annotations

import logging
import uuid
from typing import Any

from oss.forge.corpus import seed_corpus
from oss.forge.ingest import ingest_pipeline, ingest_submission
from oss.forge.quality_gate import content_hash, score_shard
from oss.forge.schemas import ForgeDomain, ForgeRunRecord, QualityTier, TrainingShard
from oss.forge.store import get_store
from oss.forge.train_bridge import export_gold, preflight_report

LOG = logging.getLogger("oss.forge.agency")


class AgencyForge:
    """
    Agency-driven training data layer.

    Cycle: ingest → score → trash filter → store gold → export for train_local.
    Feels agentic: each run is attributed, domain-tagged, genome-linked.
    """

    def __init__(self) -> None:
        self.store = get_store()

    def run_cycle(
        self,
        *,
        include_pipeline: bool = True,
        include_seeds: bool = True,
        min_tier: QualityTier = QualityTier.SILVER,
        export: bool = True,
        agent_id: str = "forge",
    ) -> ForgeRunRecord:
        run_id = uuid.uuid4().hex[:12]
        record = ForgeRunRecord(run_id=run_id, agent_id=agent_id, status="running")

        candidates: list[TrainingShard] = []
        if include_seeds:
            candidates.extend(seed_corpus())
        if include_pipeline:
            candidates.extend(ingest_pipeline())

        seen_hashes: set[str] = set()
        domain_counts: dict[str, int] = {}

        for shard in candidates:
            record.ingested += 1
            h = content_hash(shard)
            if h in seen_hashes:
                record.trashed += 1
                continue
            seen_hashes.add(h)

            verdict = score_shard(shard, min_tier=min_tier)
            if not verdict.keep:
                record.trashed += 1
                LOG.debug("trash %s tier=%s reasons=%s", shard.shard_id, verdict.tier, verdict.reasons)
                continue

            saved = self.store.save_shard(shard, verdict.tier, verdict.score, h)
            if saved:
                record.kept += 1
                domain_counts[shard.domain.value] = domain_counts.get(shard.domain.value, 0) + 1

        record.domains = domain_counts

        if export and record.kept > 0:
            manifest = export_gold(min_tier=min_tier)
            record.exported = manifest.get("exported", 0)

        record.status = "complete"
        record.notes = f"min_tier={min_tier.value} pipeline={include_pipeline} seeds={include_seeds}"
        self.store.save_run(record)
        LOG.info(
            "forge cycle %s: ingested=%d kept=%d trashed=%d exported=%d",
            run_id, record.ingested, record.kept, record.trashed, record.exported,
        )
        return record

    def submit_and_curate(
        self,
        *,
        domain: ForgeDomain,
        user: str,
        assistant: str,
        system: str = "",
        genome_id: str = "gh05t3",
    ) -> dict[str, Any]:
        shard = ingest_submission(
            domain=domain, user=user, assistant=assistant,
            system=system, genome_id=genome_id,
        )
        verdict = score_shard(shard)
        saved = False
        if verdict.keep:
            saved = self.store.save_shard(shard, verdict.tier, verdict.score, content_hash(shard))
            if saved:
                export_gold(min_tier=QualityTier.SILVER)
        return {
            "shard": shard.to_dict(),
            "verdict": verdict.to_dict(),
            "saved": saved,
        }

    def status(self) -> dict[str, Any]:
        return {
            "store": self.store.stats(),
            "preflight": preflight_report(),
            "last_run": self.store.last_run().to_dict() if self.store.last_run() else None,
        }


_agency: AgencyForge | None = None


def get_agency() -> AgencyForge:
    global _agency
    if _agency is None:
        _agency = AgencyForge()
    return _agency