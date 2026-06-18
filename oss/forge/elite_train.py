"""Elite breed training — OmniStrand export for 8B→100B effective capability."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from oss.forge.genetics import build_elite_profile, tournament_select, transcribe_strand
from oss.forge.quality_gate import score_shard
from oss.forge.schemas import ForgeDomain, QualityTier, TrainingShard
from oss.forge.store import ForgeStore, get_store

LOG = logging.getLogger("oss.forge.elite_train")

_REPO = Path(__file__).resolve().parents[2]
_EXPORT_DIR = _REPO / "backend" / "data" / "training"
_ELITE_FILE = _EXPORT_DIR / "forge_elite_strands.jsonl"
_ELITE_MANIFEST = _EXPORT_DIR / "forge_elite_manifest.json"


def strands_from_store(
    store: ForgeStore | None = None,
    *,
    min_tier: QualityTier = QualityTier.GOLD,
    top_k_per_domain: int = 12,
    physical_params_b: float = 8.0,
) -> tuple[list, dict]:
    """Genetic tournament selection → OmniStrand transcription."""
    store = store or get_store()
    tier_order = [t.value for t in QualityTier]
    min_idx = tier_order.index(min_tier.value)

    candidates: list[tuple[TrainingShard, float, QualityTier]] = []
    for shard in store.list_shards(min_tier=min_tier, limit=5000):
        verdict = score_shard(shard, min_tier=min_tier)
        if verdict.keep:
            candidates.append((shard, verdict.score, verdict.tier))

    selected = tournament_select(candidates, top_k=top_k_per_domain)
    strands = [
        transcribe_strand(shard, score, tier, rank=i)
        for i, (shard, score, tier) in enumerate(selected)
    ]
    profile = build_elite_profile(strands, physical_params_b=physical_params_b)
    return strands, profile


def export_elite_strands(
    *,
    min_tier: QualityTier = QualityTier.GOLD,
    top_k_per_domain: int = 12,
    physical_params_b: float = 8.0,
) -> dict:
    """Export genetically selected OmniStrands for train_local."""
    strands, profile = strands_from_store(
        min_tier=min_tier,
        top_k_per_domain=top_k_per_domain,
        physical_params_b=physical_params_b,
    )
    _EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    with open(_ELITE_FILE, "w", encoding="utf-8") as f:
        for strand in strands:
            f.write(json.dumps(strand.to_dict(), ensure_ascii=False) + "\n")

    manifest = {
        **profile,
        "exported": len(strands),
        "min_tier": min_tier.value,
        "output": str(_ELITE_FILE),
        "paradigm": "omni_strand_sft",
    }
    _ELITE_MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    LOG.info(
        "elite export: %d strands, effective ~%.1fB from %.1fB physical",
        len(strands),
        manifest.get("effective_capability_b", 0),
        physical_params_b,
    )
    return manifest