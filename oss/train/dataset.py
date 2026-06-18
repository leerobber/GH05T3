"""Agent-native dataset builder — forge gold, elite strands, mentor JSONL."""
from __future__ import annotations

import json
import logging
import random
from dataclasses import dataclass
from pathlib import Path

from oss.forge.omni_lex import shard_to_chatml
from oss.train.agents import AgentProfile, _DATA, agent_jsonl_paths, resolve_agent
from oss.train.schemas import TrainSource

LOG = logging.getLogger("oss.train.dataset")

_REPO = Path(__file__).resolve().parents[2]


@dataclass
class TrainExample:
    text: str
    source: str
    genome_id: str = ""
    weight: int = 1


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


def _genome_matches(profile: AgentProfile, genome_id: str, default_agent: bool) -> bool:
    g = (genome_id or "").strip()
    if not g:
        return default_agent
    return profile.matches_genome(g)


def load_forge_gold(profile: AgentProfile, *, all_agents: bool = False) -> list[TrainExample]:
    out: list[TrainExample] = []
    path = _DATA / "forge_gold.jsonl"
    for rec in _read_jsonl(path):
        text = rec.get("text", "")
        genome = rec.get("genome_id", "")
        if not text or "<|im_start|>user" not in text:
            continue
        if all_agents or _genome_matches(profile, genome, default_agent=profile.agent_id == "GH05T3"):
            out.append(TrainExample(text=text, source="forge_gold", genome_id=genome))
    return out


def load_elite_strands(profile: AgentProfile, *, all_agents: bool = False) -> list[TrainExample]:
    out: list[TrainExample] = []
    path = _DATA / "forge_elite_strands.jsonl"
    for rec in _read_jsonl(path):
        text = rec.get("chatml") or rec.get("text", "")
        genome = rec.get("genome_id", rec.get("domain", ""))
        if not text or "<|im_start|>user" not in text:
            continue
        if all_agents or _genome_matches(profile, str(genome), default_agent=profile.agent_id == "GH05T3"):
            w = int(rec.get("methylation", {}).get("transcription_weight", 1))
            out.append(
                TrainExample(
                    text=text,
                    source="elite_strand",
                    genome_id=str(genome),
                    weight=max(1, min(w, 4)),
                )
            )
    return out


def load_agent_files(profile: AgentProfile) -> list[TrainExample]:
    out: list[TrainExample] = []
    for path in agent_jsonl_paths(profile.agent_id):
        for rec in _read_jsonl(path):
            if "text" in rec and "<|im_start|>" in rec["text"]:
                out.append(TrainExample(text=rec["text"], source=path.name, genome_id=profile.agent_id))
                continue
            user = rec.get("user") or rec.get("instruction") or rec.get("prompt", "")
            assistant = rec.get("assistant") or rec.get("output") or rec.get("response", "")
            if not user or not assistant:
                continue
            system = rec.get("system") or profile.system_prompt
            from oss.forge.schemas import TrainingShard
            from oss.forge.domains import resolve_domain
            shard = TrainingShard(
                shard_id=rec.get("id", path.stem),
                domain=resolve_domain(rec.get("domain", "general_cognition")),
                system=system,
                user=user,
                assistant=assistant,
                source=path.name,
                genome_id=profile.agent_id,
            )
            out.append(
                TrainExample(
                    text=shard_to_chatml(shard),
                    source=path.name,
                    genome_id=profile.agent_id,
                )
            )
    return out


def build_examples(
    agent_id: str,
    sources: list[TrainSource],
    *,
    seed: int = 42,
) -> tuple[list[TrainExample], dict]:
    profile = resolve_agent(agent_id)
    use_all = TrainSource.ALL in sources
    active = set(sources)
    examples: list[TrainExample] = []

    if use_all or TrainSource.FORGE in active:
        examples.extend(load_forge_gold(profile, all_agents=use_all))
    if use_all or TrainSource.ELITE in active:
        examples.extend(load_elite_strands(profile, all_agents=use_all))
    if use_all or TrainSource.AGENT_FILES in active:
        examples.extend(load_agent_files(profile))

    expanded: list[TrainExample] = []
    for ex in examples:
        for _ in range(ex.weight):
            expanded.append(ex)

    if not expanded:
        raise FileNotFoundError(
            f"No training examples for agent={profile.agent_id}. "
            "Run: python oss/cli/forge_run.py --min-tier silver"
        )

    random.seed(seed)
    random.shuffle(expanded)

    by_source: dict[str, int] = {}
    for ex in expanded:
        by_source[ex.source] = by_source.get(ex.source, 0) + 1

    manifest = {
        "agent_id": profile.agent_id,
        "examples": len(expanded),
        "by_source": by_source,
        "adapter_dir": profile.adapter_dir,
    }
    LOG.info(
        "Dataset %s: %d examples %s",
        profile.agent_id, len(expanded), by_source,
    )
    return expanded, manifest