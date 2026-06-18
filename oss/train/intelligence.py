"""Intelligence Training — systems · code · data mega-dataset for GH05T3."""
from __future__ import annotations

import json
import logging
import random
from dataclasses import dataclass
from pathlib import Path

from oss.forge.omni_lex import shard_to_chatml
from oss.train.agents import _DATA, resolve_agent
from oss.train.dataset import TrainExample, load_agent_files, load_elite_strands, load_forge_gold
from oss.train.intelligence_corpus import intelligence_anchors
LOG = logging.getLogger("oss.train.intelligence")

_REPO = Path(__file__).resolve().parents[2]
_SYSTEM = (
    "You are GH05T3, an autonomous systems intelligence. "
    "You think in architectures, data flows, invariants, and falsifiable reasoning. "
    "Lead with structure, then precision."
)


@dataclass
class IntelligenceConfig:
    recall_cap: int = 2000
    reasoning_weight: int = 3
    forge_weight: int = 5
    elite_weight: int = 5
    adversarial_cap: int = 400
    min_recall_quality: int = 4
    seed: int = 42


def _read_jsonl(path: Path):
    if not path.exists():
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue


def _chatml(system: str, user: str, assistant: str) -> str:
    parts = []
    if system:
        parts.append(f"<|im_start|>system\n{system}<|im_end|>")
    parts.append(f"<|im_start|>user\n{user}<|im_end|>")
    parts.append(f"<|im_start|>assistant\n{assistant}<|im_end|>")
    return "\n".join(parts)


def load_reasoning_chains(weight: int = 2) -> list[TrainExample]:
    out: list[TrainExample] = []
    path = _DATA / "reasoning_chains.jsonl"
    for rec in _read_jsonl(path):
        q = rec.get("question", "")
        steps = rec.get("reasoning_steps", [])
        if not q or not isinstance(steps, list):
            continue
        assistant = (
            "**Reasoning:**\n" + "\n".join(f"{i+1}. {x}" for i, x in enumerate(steps)) +
            f"\n\n**Answer:** {rec.get('final_answer', 'N/A')}"
        )
        text = _chatml(_SYSTEM, q, assistant)
        for _ in range(weight):
            out.append(TrainExample(text=text, source="reasoning_chains", genome_id="GH05T3"))
    return out


def load_sovereign_recall(cfg: IntelligenceConfig) -> list[TrainExample]:
    path = _DATA / "sovereign_recall.jsonl"
    pool: list[dict] = []
    max_chars = 12_000  # pre-filter monster turns before tokenize
    for rec in _read_jsonl(path):
        text = rec.get("text", "")
        if not text or rec.get("quality", 0) < cfg.min_recall_quality:
            continue
        if "<|im_start|>user" not in text or "<|im_start|>assistant" not in text:
            continue
        if len(text) > max_chars:
            text = text[:max_chars] + "\n<|im_end|>"
            rec = {**rec, "text": text}
        pool.append(rec)
    rng = random.Random(cfg.seed)
    rng.shuffle(pool)
    selected = pool[: cfg.recall_cap]
    return [
        TrainExample(text=r["text"], source="sovereign_recall", genome_id="GH05T3")
        for r in selected
    ]


def load_adversarial_systems(cfg: IntelligenceConfig) -> list[TrainExample]:
    out: list[TrainExample] = []
    path = _DATA / "adversarial_defense.jsonl"
    pool = list(_read_jsonl(path))
    rng = random.Random(cfg.seed + 1)
    rng.shuffle(pool)
    for rec in pool[: cfg.adversarial_cap]:
        t = rec.get("threat_vector", "")
        if not t:
            continue
        assistant = (
            f"**Exploitation:** {rec.get('exploitation_method', 'N/A')}\n\n"
            f"**Detection:** {rec.get('detection_pattern', 'N/A')}\n\n"
            f"**Mitigation:** {rec.get('mitigation_strategy', 'N/A')}"
        )
        text = _chatml(_SYSTEM, f"Analyze threat:\n\n{t}", assistant)
        out.append(TrainExample(text=text, source="adversarial_defense", genome_id="SENTINEL"))
    return out


def build_intelligence_dataset(
    agent_id: str = "GH05T3",
    cfg: IntelligenceConfig | None = None,
) -> tuple[list[TrainExample], dict]:
    """Mega-dataset optimized for systems, code, and data reasoning."""
    cfg = cfg or IntelligenceConfig()
    profile = resolve_agent(agent_id)
    examples: list[TrainExample] = []

    # Forge + elite — all agents, heavily weighted
    for ex in load_forge_gold(profile, all_agents=True):
        for _ in range(cfg.forge_weight):
            examples.append(ex)
    for ex in load_elite_strands(profile, all_agents=True):
        for _ in range(cfg.elite_weight):
            examples.append(ex)

    examples.extend(load_reasoning_chains(weight=cfg.reasoning_weight))
    examples.extend(load_sovereign_recall(cfg))
    examples.extend(load_adversarial_systems(cfg))

    for text, weight in intelligence_anchors():
        for _ in range(weight):
            examples.append(TrainExample(text=text, source="intelligence_anchor", genome_id="GH05T3"))

    mentor = load_agent_files(profile)
    examples.extend(mentor)

    if not examples:
        raise FileNotFoundError("Intelligence dataset empty — run forge export first")

    rng = random.Random(cfg.seed)
    rng.shuffle(examples)

    by_source: dict[str, int] = {}
    for ex in examples:
        by_source[ex.source] = by_source.get(ex.source, 0) + 1

    manifest = {
        "profile": "intelligence_systems_code_data",
        "agent_id": profile.agent_id,
        "examples": len(examples),
        "by_source": by_source,
        "config": {
            "recall_cap": cfg.recall_cap,
            "reasoning_weight": cfg.reasoning_weight,
            "forge_weight": cfg.forge_weight,
        },
        "domains": [
            "systems_engineering", "computational_science", "statistical_inference",
            "agentic_systems", "theoretical_cs", "data_pipelines", "security_systems",
        ],
        "mentor_examples": len(mentor),
    }
    LOG.info("Intelligence dataset: %d examples %s", len(examples), by_source)
    return examples, manifest