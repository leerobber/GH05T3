"""Safe training bridge — preflight checks + export to train_local format."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from oss.forge.omni_lex import shard_to_chatml
from oss.forge.schemas import ForgeDomain, QualityTier, TrainingShard
from oss.forge.store import get_store
from oss.substrate.attention_config import AttentionConfig

LOG = logging.getLogger("oss.forge.train_bridge")

_REPO = Path(__file__).resolve().parents[2]
_EXPORT_DIR = _REPO / "backend" / "data" / "training"
_GOLD_FILE = _EXPORT_DIR / "forge_gold.jsonl"
_MANIFEST = _EXPORT_DIR / "forge_manifest.json"

# NON-NEGOTIABLE training rules (from Claude.md) — enforced at preflight
_PREFLIGHT_RULES = (
    "RULE 1: Never cast LoRA adapters to fp16 after get_peft_model()",
    "RULE 2: gradient_checkpointing_kwargs use_reentrant=False",
    "RULE 3: Collapse detection 0.3 < loss < 10 before save",
    "RULE 4: Local RTX 5050 only — no P100/Kaggle",
)


def preflight_report() -> dict:
    """Return training safety checklist for agency runs."""
    import subprocess
    import sys

    py = _REPO / "backend" / ".venv" / "Scripts" / "python.exe"
    checks: dict[str, str] = {}

    if not py.exists():
        py = Path(sys.executable)

    for pkg in ("torch", "peft", "transformers", "trl", "datasets"):
        r = subprocess.run([str(py), "-c", f"import {pkg}"], capture_output=True)
        checks[pkg] = "ok" if r.returncode == 0 else "missing"

    try:
        import torch
        checks["cuda"] = "ok" if torch.cuda.is_available() else "cpu_only"
        if torch.cuda.is_available():
            major, _ = torch.cuda.get_device_capability(0)
            checks["gpu_sm"] = str(major)
            if major == 6:
                checks["gpu_sm"] = "BLOCKED_P100"
    except Exception as exc:
        checks["cuda"] = f"error:{exc}"

    adapter = _REPO / "backend" / "models" / "gh05t3_lora_adapter"
    checks["adapter_dir"] = "ok" if adapter.exists() else "missing"

    return {
        "rules": list(_PREFLIGHT_RULES),
        "checks": checks,
        "ready": checks.get("torch") == "ok"
        and checks.get("peft") == "ok"
        and checks.get("gpu_sm") != "BLOCKED_P100",
    }


def _attention_config_for_shard(shard: TrainingShard) -> dict:
    """Derive an AttentionConfig dict for a shard, using genome substrate when available."""
    try:
        from oss.substrate.genomic import get_substrate
        substrate = get_substrate()
        seg = substrate.segment(shard.genome_id) if shard.genome_id else None
        if seg is not None and seg.attention_config is not None:
            return seg.attention_config.to_dict()
        traits = seg.traits if seg is not None else {}
    except Exception:
        traits = {}
    return AttentionConfig.from_genome_traits(traits, shard.genome_id).to_dict()


def export_gold(
    min_tier: QualityTier = QualityTier.SILVER,
    domain: ForgeDomain | None = None,
) -> dict:
    """Export curated shards to forge_gold.jsonl for train_local consumption."""
    store = get_store()
    shards = store.list_shards(min_tier=min_tier, domain=domain, limit=10_000)
    _EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    seen: set[str] = set()
    exported = 0
    by_domain: dict[str, int] = {}

    with open(_GOLD_FILE, "w", encoding="utf-8") as f:
        for shard in shards:
            key = f"{shard.user[:80]}|{shard.assistant[:80]}"
            if key in seen:
                continue
            seen.add(key)
            attn_cfg = _attention_config_for_shard(shard)
            record = {
                "text": shard_to_chatml(shard),
                "domain": shard.domain.value,
                "genome_id": shard.genome_id,
                "source": shard.source,
                "shard_id": shard.shard_id,
                "attention_config": attn_cfg,
                "attention_backend": attn_cfg.get("backend", "auto"),
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            exported += 1
            by_domain[shard.domain.value] = by_domain.get(shard.domain.value, 0) + 1

    manifest = {
        "exported": exported,
        "min_tier": min_tier.value,
        "domain_filter": domain.value if domain else None,
        "output": str(_GOLD_FILE),
        "by_domain": by_domain,
    }
    _MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    LOG.info("exported %d shards to %s", exported, _GOLD_FILE)
    return manifest