"""Domain research training — Rob rotation domains + SPIN + sovereign_nation."""
from __future__ import annotations

import json
import logging
import random
import re
from dataclasses import dataclass, field
from pathlib import Path

from ghost_domains import DOMAINS, get_domain

from oss.train.dataset import TrainExample

LOG = logging.getLogger("oss.train.domain_research")

_REPO = Path(__file__).resolve().parents[2]

# Domains Robert pasted for continuous_learner / Rob training rotation
ROB_DOMAIN_SLUGS: tuple[str, ...] = (
    "business",
    "sales",
    "product_strategy",
    "growth",
    "cfo",
    "content",
    "legal_ip",
    "ops",
    "ml_engineer",
    "frontier",
    "core",
)

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


@dataclass
class DomainResearchConfig:
    domain_slugs: tuple[str, ...] = ROB_DOMAIN_SLUGS
    goals_per_domain: int = 12
    spin_cap: int = 400
    spin_min_chars: int = 180
    weight_spin: int = 3
    weight_sovereign: int = 5
    weight_goal: int = 2
    seed: int = 42
    extra_slugs: tuple[str, ...] = field(default_factory=tuple)


def _chatml(system: str, user: str, assistant: str) -> str:
    parts = []
    if system:
        parts.append(f"<|im_start|>system\n{system}<|im_end|>")
    parts.append(f"<|im_start|>user\n{user}<|im_end|>")
    parts.append(f"<|im_start|>assistant\n{assistant}<|im_end|>")
    return "\n".join(parts)


def _strip_think(text: str) -> str:
    t = _THINK_RE.sub("", text or "").strip()
    if t.startswith("<think>"):
        for marker in ("**PROPOSAL:", "## ", "# ", "\n\n"):
            idx = t.find(marker, 20)
            if idx != -1:
                return t[idx:].strip()
    return t


def _synthesize_assistant(domain_data: dict, goal: str) -> str:
    seeds = domain_data.get("wisdom_seeds", [])[:3]
    rubric = (domain_data.get("rubric_context") or "")[:500]
    return (
        f"**Objective:** {goal}\n\n"
        f"**Domain:** {domain_data.get('description', '')}\n\n"
        f"**Principles:**\n"
        + "\n".join(f"- {s}" for s in seeds)
        + "\n\n"
        "**Deliverable:**\n"
        "1. Repo-grounded foundation (sovereign-core, hyper-agent, openclaw, avery)\n"
        "2. Named ICP / customer segment with concrete pain\n"
        "3. Numbered execution steps runnable this week\n"
        "4. Measurable success metric + verification\n"
        "5. Risks and rollback plan\n\n"
        f"**Quality bar:** {rubric}"
    )


def load_sovereign_nation_research() -> list[TrainExample]:
    """Curated SovereignNation strategy Q&A (pasted research corpus)."""
    paths = [
        _REPO / "training_data" / "domain_research" / "sovereign_nation.jsonl",
        _REPO / "data" / "domain_research" / "sovereign_nation.jsonl",
    ]
    out: list[TrainExample] = []
    system = (
        "You are Avery (GH05T3), founder intelligence for SovereignNation. "
        "Ground every answer in affordability, repo assets, and measurable outcomes."
    )
    for path in paths:
        if not path.exists():
            continue
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                msgs = rec.get("messages") or []
                user = next((m["content"] for m in msgs if m.get("role") == "user"), "")
                assistant = next((m["content"] for m in msgs if m.get("role") == "assistant"), "")
                if not user or not assistant:
                    continue
                out.append(
                    TrainExample(
                        text=_chatml(system, user, assistant),
                        source="sovereign_nation_research",
                        genome_id="GH05T3",
                    )
                )
        break
    return out


def _spin_domain_slug(rec: dict) -> str:
    d = (rec.get("domain") or "").lower().strip()
    if d:
        return d.replace(" ", "_")
    blob = f"{rec.get('goal', '')} {rec.get('chosen', '')}".lower()
    for slug in ROB_DOMAIN_SLUGS:
        if slug.replace("_", " ") in blob or slug in blob:
            return slug
    if "domain:" in blob:
        m = re.search(r"domain:\s*(\w+)", blob, re.I)
        if m:
            return m.group(1).lower()
    return "core"


def load_spin_domain_pairs(cfg: DomainResearchConfig) -> list[TrainExample]:
    path = _REPO / "data" / "spin_dataset.jsonl"
    if not path.exists():
        return []
    allowed = set(cfg.domain_slugs) | set(cfg.extra_slugs)
    pool: list[tuple[str, str, str]] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            slug = _spin_domain_slug(rec)
            if slug not in allowed and slug not in DOMAINS:
                continue
            goal = (rec.get("goal") or "").strip()
            chosen = _strip_think(rec.get("chosen") or "")
            if not goal or len(chosen) < cfg.spin_min_chars:
                continue
            if chosen.startswith("[ERR"):
                continue
            try:
                dom = get_domain(slug if slug in DOMAINS else "core")
                system = dom["persona"]
            except ValueError:
                system = "You are GH05T3, strategic intelligence for SovereignNation."
            pool.append((system, goal, chosen[:8000]))

    rng = random.Random(cfg.seed)
    rng.shuffle(pool)
    selected = pool[: cfg.spin_cap]
    out: list[TrainExample] = []
    for system, goal, chosen in selected:
        text = _chatml(system, goal, chosen)
        for _ in range(cfg.weight_spin):
            out.append(
                TrainExample(text=text, source="spin_domain", genome_id="GH05T3"),
            )
    return out


def load_ghost_domain_goals(cfg: DomainResearchConfig) -> list[TrainExample]:
    slugs = tuple(dict.fromkeys((*cfg.domain_slugs, *cfg.extra_slugs)))
    out: list[TrainExample] = []
    rng = random.Random(cfg.seed + 7)

    for slug in slugs:
        if slug not in DOMAINS:
            LOG.warning("Unknown domain slug skipped: %s", slug)
            continue
        dom = get_domain(slug)
        system = dom["persona"]
        goals = list(dom.get("goals") or [])
        rng.shuffle(goals)
        for goal in goals[: cfg.goals_per_domain]:
            assistant = _synthesize_assistant(dom, goal)
            text = _chatml(system, goal, assistant)
            for _ in range(cfg.weight_goal):
                out.append(
                    TrainExample(
                        text=text,
                        source=f"ghost_domain_{slug}",
                        genome_id="GH05T3",
                    )
                )
    return out


def build_domain_research_dataset(
    cfg: DomainResearchConfig | None = None,
) -> tuple[list[TrainExample], dict]:
    cfg = cfg or DomainResearchConfig()
    examples: list[TrainExample] = []

    sovereign = load_sovereign_nation_research()
    for ex in sovereign:
        for _ in range(cfg.weight_sovereign):
            examples.append(ex)

    examples.extend(load_spin_domain_pairs(cfg))
    examples.extend(load_ghost_domain_goals(cfg))

    if not examples:
        raise FileNotFoundError(
            "Domain research dataset empty — check data/spin_dataset.jsonl and ghost_domains.py"
        )

    rng = random.Random(cfg.seed)
    rng.shuffle(examples)

    by_source: dict[str, int] = {}
    for ex in examples:
        by_source[ex.source] = by_source.get(ex.source, 0) + 1

    manifest = {
        "profile": "domain_research_rob_rotation",
        "examples": len(examples),
        "by_source": by_source,
        "domain_slugs": list(cfg.domain_slugs),
        "config": {
            "goals_per_domain": cfg.goals_per_domain,
            "spin_cap": cfg.spin_cap,
            "weight_spin": cfg.weight_spin,
            "weight_sovereign": cfg.weight_sovereign,
        },
    }
    LOG.info("Domain research dataset: %d examples %s", len(examples), by_source)
    return examples, manifest