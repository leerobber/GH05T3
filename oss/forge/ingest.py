"""Ingest training material from pipeline datasets, recall, and submissions."""
from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import Iterator

from oss.forge.schemas import ForgeDomain, TrainingShard

LOG = logging.getLogger("oss.forge.ingest")

_REPO = Path(__file__).resolve().parents[2]
_PIPELINE_DATASETS = _REPO / "backend" / "training" / "datasets"
_LEGACY_DATA = _REPO / "backend" / "data" / "training"
_RECALL = _LEGACY_DATA / "sovereign_recall.jsonl"

_DOMAIN_MAP = {
    "adversarial_defense": ForgeDomain.SECURITY,
    "cve_patterns": ForgeDomain.SECURITY,
    "bug_bounty": ForgeDomain.SECURITY,
    "reasoning_chains": ForgeDomain.RESEARCH,
    "sovereign_recall": ForgeDomain.RESEARCH,
}

_SYSTEM_DEFAULT = (
    "You are GH05T3, an autonomous reasoning agent. Think step-by-step with rigor."
)


def _iter_jsonl(path: Path) -> Iterator[dict]:
    if not path.exists():
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def _from_pipeline_record(name: str, rec: dict) -> TrainingShard | None:
    domain = _DOMAIN_MAP.get(name, ForgeDomain.DEFAULT)
    if name == "adversarial_defense":
        user = rec.get("threat_vector", "")
        if not user:
            return None
        assistant = (
            f"**Exploitation:** {rec.get('exploitation_method', 'N/A')}\n\n"
            f"**Detection:** {rec.get('detection_pattern', 'N/A')}\n\n"
            f"**Mitigation:** {rec.get('mitigation_strategy', 'N/A')}"
        )
    elif name == "reasoning_chains":
        user = rec.get("question", "")
        steps = rec.get("reasoning_steps", [])
        if not user or not isinstance(steps, list):
            return None
        assistant = (
            "**Reasoning:**\n" + "\n".join(f"{i+1}. {s}" for i, s in enumerate(steps))
            + f"\n\n**Answer:** {rec.get('final_answer', 'N/A')}"
        )
    elif name == "cve_patterns":
        user = f"Analyze {rec.get('source_cve', 'CVE')} vulnerability pattern."
        assistant = (
            f"**Pattern:** {rec.get('vulnerability_pattern', 'N/A')}\n\n"
            f"**Lessons:** {rec.get('defensive_lessons', 'N/A')}"
        )
    elif name == "bug_bounty":
        user = f"Security research: {rec.get('target_system', '')} — {rec.get('vulnerability_found', '')}"
        if not rec.get("target_system"):
            return None
        assistant = (
            f"**Recon:** {rec.get('recon_method', 'N/A')}\n\n"
            f"**Remediation:** {rec.get('remediation', 'N/A')}"
        )
    else:
        return None

    sid = uuid.uuid5(uuid.NAMESPACE_URL, f"{name}:{user[:200]}").hex[:16]
    return TrainingShard(
        shard_id=sid,
        domain=domain,
        system=_SYSTEM_DEFAULT,
        user=user.strip(),
        assistant=assistant.strip(),
        source=f"pipeline:{name}",
        tags=[name],
    )


def _from_recall(rec: dict) -> TrainingShard | None:
    text = rec.get("text", "")
    quality = rec.get("quality", 0)
    if quality < 4 or "<|im_start|>user" not in text:
        return None
    user_part = assistant_part = ""
    if "<|im_start|>user" in text:
        try:
            user_part = text.split("<|im_start|>user", 1)[1].split("<|im_end|>", 1)[0].strip()
            rest = text.split("<|im_end|>", 1)[-1]
            if "<|im_start|>assistant" in rest:
                assistant_part = rest.split("<|im_start|>assistant", 1)[1].split("<|im_end|>", 1)[0].strip()
        except IndexError:
            return None
    if not user_part or not assistant_part:
        return None
    sid = uuid.uuid5(uuid.NAMESPACE_URL, f"recall:{user_part[:120]}").hex[:16]
    return TrainingShard(
        shard_id=sid,
        domain=ForgeDomain.RESEARCH,
        system=_SYSTEM_DEFAULT,
        user=user_part,
        assistant=assistant_part,
        source="sovereign_recall",
        tags=["recall"],
        metadata={"recall_quality": quality},
    )


def ingest_pipeline(max_per_file: int = 500) -> list[TrainingShard]:
    shards: list[TrainingShard] = []
    for path in sorted(_PIPELINE_DATASETS.glob("*.jsonl")):
        count = 0
        for rec in _iter_jsonl(path):
            shard = _from_pipeline_record(path.stem, rec)
            if shard:
                shards.append(shard)
                count += 1
            if count >= max_per_file:
                break
        LOG.info("ingested %d from %s", count, path.name)

    if _LEGACY_DATA.exists():
        for path in sorted(_LEGACY_DATA.glob("*.jsonl")):
            if path.name == "sovereign_recall.jsonl":
                continue
            count = 0
            for rec in _iter_jsonl(path):
                shard = _from_pipeline_record(path.stem, rec)
                if shard:
                    shards.append(shard)
                    count += 1
                if count >= max_per_file:
                    break

    recall_count = 0
    for rec in _iter_jsonl(_RECALL):
        shard = _from_recall(rec)
        if shard:
            shards.append(shard)
            recall_count += 1
    LOG.info("ingested %d from sovereign_recall", recall_count)
    return shards


def ingest_submission(
    *,
    domain: ForgeDomain,
    user: str,
    assistant: str,
    system: str = "",
    genome_id: str = "gh05t3",
    tags: list[str] | None = None,
) -> TrainingShard:
    sid = uuid.uuid4().hex[:16]
    return TrainingShard(
        shard_id=sid,
        domain=domain,
        system=system or _SYSTEM_DEFAULT,
        user=user.strip(),
        assistant=assistant.strip(),
        source="api_submission",
        genome_id=genome_id,
        tags=tags or ["submission"],
    )