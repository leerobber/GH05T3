"""Agent training registry — maps sovereign agents to adapters and system prompts."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_MODELS = _REPO / "backend" / "models"
_DATA = _REPO / "backend" / "data" / "training"
_AGENT_JSONL = _REPO / "training_data" / "agent_training"


@dataclass(frozen=True)
class AgentProfile:
    agent_id: str
    display_name: str
    adapter_dir: str
    system_prompt: str
    genome_aliases: tuple[str, ...] = ()

    @property
    def output_path(self) -> Path:
        return _MODELS / self.adapter_dir

    def matches_genome(self, genome_id: str) -> bool:
        g = (genome_id or "").strip().upper()
        if not g:
            return False
        keys = {self.agent_id.upper(), *(a.upper() for a in self.genome_aliases)}
        return g in keys


AGENT_PROFILES: dict[str, AgentProfile] = {
    "GH05T3": AgentProfile(
        agent_id="GH05T3",
        display_name="Avery / GH05T3",
        adapter_dir="gh05t3_lora_adapter",
        genome_aliases=("AVERY", "GH05T3"),
        system_prompt=(
            "You are GH05T3, an autonomous security and reasoning agent. "
            "You think carefully, reason step-by-step, and always prioritize "
            "detection and defense over exploitation."
        ),
    ),
    "FORGE": AgentProfile(
        agent_id="FORGE",
        display_name="Marcus Reid / FORGE",
        adapter_dir="code_adapter",
        genome_aliases=("MARCUS", "CODEX"),
        system_prompt=(
            "You are FORGE, GH05T3's CTO. You write clean, efficient, well-reasoned code. "
            "You perform deep code reviews, architectural analysis, refactoring, and "
            "debugging. You explain your reasoning step-by-step before writing code."
        ),
    ),
    "ORACLE": AgentProfile(
        agent_id="ORACLE",
        display_name="Iris Chen / ORACLE",
        adapter_dir="research_adapter",
        genome_aliases=("IRIS",),
        system_prompt=(
            "You are ORACLE, GH05T3's Chief Research Officer. "
            "You synthesize complex information, compare methodologies, survey literature, "
            "and produce comprehensive, well-structured research summaries."
        ),
    ),
    "SENTINEL": AgentProfile(
        agent_id="SENTINEL",
        display_name="Viktor Steele / SENTINEL",
        adapter_dir="security_adapter",
        genome_aliases=("VIKTOR",),
        system_prompt=(
            "You are SENTINEL, GH05T3's Chief Security Officer. "
            "You specialize in threat analysis, CVE research, vulnerability assessment, "
            "and defensive security architecture."
        ),
    ),
    "NEXUS": AgentProfile(
        agent_id="NEXUS",
        display_name="Kai Okafor / NEXUS",
        adapter_dir="ops_adapter",
        genome_aliases=("KAI",),
        system_prompt=(
            "You are NEXUS, GH05T3's COO. You manage infrastructure, deployments, "
            "incident response, capacity planning, and operational excellence."
        ),
    ),
    "CODEX": AgentProfile(
        agent_id="CODEX",
        display_name="Zoe Nakamura / CODEX",
        adapter_dir="research_adapter",
        genome_aliases=("ZOE",),
        system_prompt=(
            "You are CODEX, GH05T3's VP Engineering. You produce precise documentation, "
            "API specs, runbooks, and technical writing with clarity and completeness."
        ),
    ),
}


def resolve_agent(agent_id: str) -> AgentProfile:
    key = (agent_id or "GH05T3").strip().upper()
    if key in AGENT_PROFILES:
        return AGENT_PROFILES[key]
    for profile in AGENT_PROFILES.values():
        if profile.matches_genome(key):
            return profile
    return AGENT_PROFILES["GH05T3"]


def list_agents() -> list[dict]:
    return [
        {
            "agent_id": p.agent_id,
            "display_name": p.display_name,
            "adapter_dir": p.adapter_dir,
            "output_path": str(p.output_path),
        }
        for p in AGENT_PROFILES.values()
    ]


def agent_jsonl_paths(agent_id: str) -> list[Path]:
    """Per-agent mentor JSONL files if present."""
    profile = resolve_agent(agent_id)
    if not _AGENT_JSONL.exists():
        return []
    paths = []
    for pattern in (
        f"{profile.agent_id.lower()}_*.jsonl",
        f"{profile.display_name.split()[0].lower()}_*.jsonl",
    ):
        paths.extend(_AGENT_JSONL.glob(pattern))
    return sorted(set(paths))