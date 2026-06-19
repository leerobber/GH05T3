"""Civilization Kernel agents — five roles × three stages (Base → Specialist → Frontier)."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from oss.kernel.shards import ROLE_PRIMARY_SHARDS, SHARD_CATALOG, ShardType
from oss.kernel.schemas import HeartbeatPhase


class AgentRole(str, Enum):
    SCIENTIST = "scientist"
    INVESTOR = "investor"
    OPERATOR = "operator"
    GOVERNOR = "governor"
    BUILDER = "builder"


class AgentStage(str, Enum):
    BASE = "base"
    SPECIALIST = "specialist"
    FRONTIER = "frontier"


# Heartbeat phase → responsible agent
PHASE_AGENT: dict[HeartbeatPhase, AgentRole] = {
    HeartbeatPhase.RESEARCH: AgentRole.SCIENTIST,
    HeartbeatPhase.MONETIZE: AgentRole.BUILDER,
    HeartbeatPhase.TREASURY: AgentRole.INVESTOR,
    HeartbeatPhase.INVEST: AgentRole.INVESTOR,
    HeartbeatPhase.FUND: AgentRole.OPERATOR,
    HeartbeatPhase.IMPROVE: AgentRole.OPERATOR,
    HeartbeatPhase.GOVERN: AgentRole.GOVERNOR,
}

# LoRA adapter directory per role (MoE bucket root)
ROLE_ADAPTER_DIRS: dict[AgentRole, str] = {
    AgentRole.SCIENTIST: "research_adapter",
    AgentRole.INVESTOR: "domain_research_adapter",
    AgentRole.OPERATOR: "ops_adapter",
    AgentRole.GOVERNOR: "security_adapter",
    AgentRole.BUILDER: "domain_research_adapter",
}

# Legacy persona bridge (GH05T3 team ↔ civilization roles)
PERSONA_BRIDGE: dict[AgentRole, str] = {
    AgentRole.SCIENTIST: "ORACLE",
    AgentRole.INVESTOR: "AVERY",
    AgentRole.OPERATOR: "FORGE",
    AgentRole.GOVERNOR: "SENTINEL",
    AgentRole.BUILDER: "NEXUS",
}


@dataclass(frozen=True)
class StageSpec:
    stage: AgentStage
    title: str
    shards: tuple[ShardType, ...]
    data_types: tuple[str, ...]
    tasks: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage.value,
            "title": self.title,
            "shards": [s.value for s in self.shards],
            "shard_details": [SHARD_CATALOG[s].to_dict() for s in self.shards if s in SHARD_CATALOG],
            "data_types": list(self.data_types),
            "tasks": list(self.tasks),
        }


@dataclass(frozen=True)
class AgentSpec:
    role: AgentRole
    core_purpose: str
    primary_shards: tuple[ShardType, ...]
    stages: tuple[StageSpec, ...]
    persona: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role.value,
            "core_purpose": self.core_purpose,
            "persona": self.persona or PERSONA_BRIDGE.get(self.role, ""),
            "primary_shards": [s.value for s in self.primary_shards],
            "adapter_dir": ROLE_ADAPTER_DIRS.get(self.role, "gh05t3_lora_adapter"),
            "stages": [st.to_dict() for st in self.stages],
        }


AGENT_REGISTRY: dict[AgentRole, AgentSpec] = {
    AgentRole.SCIENTIST: AgentSpec(
        role=AgentRole.SCIENTIST,
        core_purpose="Discover, model, and theorize",
        primary_shards=ROLE_PRIMARY_SHARDS["scientist"],
        persona="ORACLE",
        stages=(
            StageSpec(
                AgentStage.BASE,
                "Base generalist",
                (ShardType.WORLD_MODEL, ShardType.CODE),
                (
                    "intro scientific articles", "textbooks", "tutorials",
                    "classical mechanics simulations", "basic ODEs",
                    "math problem sets and solutions",
                ),
                (
                    "summarize introductory science",
                    "run simple simulations",
                    "solve math problem sets",
                ),
            ),
            StageSpec(
                AgentStage.SPECIALIST,
                "Domain scientist",
                (ShardType.SCIENTIFIC_TEXT, ShardType.SIMULATION),
                (
                    "full research papers + abstracts + citations",
                    "simulation datasets with parameters + outputs",
                    "experimental datasets with error bars and protocols",
                ),
                (
                    "summarize, critique, and extend papers",
                    "predict experiment/simulation outcomes",
                    "generate hypotheses from data patterns",
                ),
            ),
            StageSpec(
                AgentStage.FRONTIER,
                "Frontier theorist",
                (ShardType.FRONTIER_SIMULATION, ShardType.META_SCIENCE, ShardType.GOVERNANCE),
                (
                    "high-dimensional simulations", "chaotic systems", "coupled models",
                    "meta-analyses", "systematic reviews", "research guidelines",
                ),
                (
                    "design new experiments and simulations",
                    "propose novel models and theories",
                    "evaluate risk and impact of research directions",
                ),
            ),
        ),
    ),
    AgentRole.INVESTOR: AgentSpec(
        role=AgentRole.INVESTOR,
        core_purpose="Allocate capital, manage risk",
        primary_shards=ROLE_PRIMARY_SHARDS["investor"],
        persona="AVERY",
        stages=(
            StageSpec(
                AgentStage.BASE,
                "Base economic thinker",
                (ShardType.WORLD_MODEL, ShardType.MARKETS),
                (
                    "historical prices (daily/weekly)",
                    "basic macro data (GDP, inflation, unemployment)",
                    "intro finance and economics texts",
                ),
                (
                    "recognize trends and cycles",
                    "explain basic portfolio concepts",
                    "simulate simple buy/hold strategies",
                ),
            ),
            StageSpec(
                AgentStage.SPECIALIST,
                "Market & on-chain specialist",
                (ShardType.ADVANCED_MARKETS, ShardType.ON_CHAIN, ShardType.RISK),
                (
                    "tick data", "order book snapshots", "liquidity metrics",
                    "smart contract interactions", "token flows", "pool states",
                    "historical crises", "regime shifts", "black swans",
                ),
                (
                    "design and backtest strategies",
                    "model liquidity, slippage, and execution risk",
                    "evaluate DeFi positions and governance proposals",
                ),
            ),
            StageSpec(
                AgentStage.FRONTIER,
                "Treasury & macro allocator",
                (ShardType.MACRO_STRATEGY, ShardType.GOVERNANCE, ShardType.WORLD_MODEL),
                (
                    "multi-asset portfolios", "factor models", "scenario analyses",
                    "institutional risk policies", "capital allocation memos",
                ),
                (
                    "allocate treasury across strategies and horizons",
                    "balance growth vs resilience",
                    "coordinate with Governor on constraints",
                ),
            ),
        ),
    ),
    AgentRole.OPERATOR: AgentSpec(
        role=AgentRole.OPERATOR,
        core_purpose="Build and run systems & infra",
        primary_shards=ROLE_PRIMARY_SHARDS["operator"],
        persona="FORGE",
        stages=(
            StageSpec(
                AgentStage.BASE,
                "Base engineer",
                (ShardType.CODE, ShardType.OPERATIONS),
                (
                    "repos", "CI configs", "Dockerfiles", "infra scripts",
                    "logs from simple services", "uptime metrics",
                ),
                (
                    "write and debug code",
                    "deploy small services",
                    "set up basic monitoring",
                ),
            ),
            StageSpec(
                AgentStage.SPECIALIST,
                "Systems & infra operator",
                (ShardType.AGENCY_TOOLS, ShardType.ADVANCED_OPERATIONS, ShardType.SECURITY),
                (
                    "complex infra configs", "orchestration (Kubernetes)",
                    "multi-service logs", "incident reports", "postmortems",
                    "access control policies", "security playbooks",
                ),
                (
                    "orchestrate tools and services for other agents",
                    "maintain uptime and performance",
                    "respond to incidents and adapt infra",
                ),
            ),
            StageSpec(
                AgentStage.FRONTIER,
                "Platform steward",
                (ShardType.CROSS_ROLE, ShardType.GOVERNANCE),
                (
                    "cross-agent workflows", "dependency graphs",
                    "platform roadmaps", "capacity planning docs",
                ),
                (
                    "design and evolve platform architecture",
                    "prioritize infra investments",
                    "coordinate with Governor on operational constraints",
                ),
            ),
        ),
    ),
    AgentRole.GOVERNOR: AgentSpec(
        role=AgentRole.GOVERNOR,
        core_purpose="Set rules, constraints, and alignment",
        primary_shards=ROLE_PRIMARY_SHARDS["governor"],
        persona="SENTINEL",
        stages=(
            StageSpec(
                AgentStage.BASE,
                "Rule-aware generalist",
                (ShardType.GOVERNANCE, ShardType.WORLD_MODEL),
                (
                    "codes of conduct", "basic legal principles",
                    "intro ethics and governance texts",
                ),
                (
                    "identify obvious violations",
                    "explain basic constraints and norms",
                ),
            ),
            StageSpec(
                AgentStage.SPECIALIST,
                "Governance & law specialist",
                (ShardType.LEGAL, ShardType.GOVERNANCE, ShardType.MARKETS),
                (
                    "governance proposals", "voting outcomes", "charters",
                    "compliance guidelines", "risk policies",
                ),
                (
                    "draft and interpret rules for the AI system",
                    "evaluate proposals from other agents",
                    "balance innovation vs safety",
                ),
            ),
            StageSpec(
                AgentStage.FRONTIER,
                "Constitutional meta-governor",
                (ShardType.META_ALIGNMENT, ShardType.CROSS_ROLE),
                (
                    "alignment research", "constitutional AI frameworks",
                    "historical incidents", "near-misses", "mitigations",
                ),
                (
                    "maintain and evolve the system constitution",
                    "set guardrails for Investor, Scientist, Operator, Builder",
                    "monitor emergent risks and intervene",
                ),
            ),
        ),
    ),
    AgentRole.BUILDER: AgentSpec(
        role=AgentRole.BUILDER,
        core_purpose="Create products, services, monetization",
        primary_shards=ROLE_PRIMARY_SHARDS["builder"],
        persona="NEXUS",
        stages=(
            StageSpec(
                AgentStage.BASE,
                "Product-aware generalist",
                (ShardType.OPERATIONS, ShardType.WORLD_MODEL),
                (
                    "landing pages", "onboarding flows", "pricing pages",
                    "case studies of products and services",
                ),
                (
                    "describe product ideas",
                    "sketch basic user journeys",
                    "write simple copy and specs",
                ),
            ),
            StageSpec(
                AgentStage.SPECIALIST,
                "Monetization & UX specialist",
                (ShardType.ADVANCED_OPERATIONS, ShardType.MARKETS, ShardType.AGENCY_TOOLS),
                (
                    "product analytics", "funnels", "retention metrics",
                    "API docs", "integration guides",
                ),
                (
                    "design revenue-generating services",
                    "optimize pricing and packaging",
                    "coordinate with Operator to deploy offerings",
                ),
            ),
            StageSpec(
                AgentStage.FRONTIER,
                "Ecosystem architect",
                (ShardType.CROSS_ROLE, ShardType.GOVERNANCE),
                (
                    "platform ecosystem maps", "partner models", "multi-sided markets",
                    "policies on user rights", "data use", "revenue sharing",
                ),
                (
                    "design the overall economic ecosystem",
                    "ensure sustainability and alignment with constitution",
                    "create business lines that fund treasury and research",
                ),
            ),
        ),
    ),
}


def list_agents() -> list[dict[str, Any]]:
    return [a.to_dict() for a in AGENT_REGISTRY.values()]


def agent_for_role(role: str) -> AgentSpec | None:
    try:
        return AGENT_REGISTRY[AgentRole(role)]
    except (KeyError, ValueError):
        return None


def agent_for_phase(phase: HeartbeatPhase) -> AgentRole:
    return PHASE_AGENT.get(phase, AgentRole.OPERATOR)


def stage_spec(role: AgentRole, stage: AgentStage) -> StageSpec | None:
    spec = AGENT_REGISTRY.get(role)
    if not spec:
        return None
    for st in spec.stages:
        if st.stage == stage:
            return st
    return None


def shards_for_agent_stage(role: AgentRole, stage: AgentStage) -> list[dict[str, Any]]:
    st = stage_spec(role, stage)
    if not st:
        return []
    return [SHARD_CATALOG[s].to_dict() for s in st.shards if s in SHARD_CATALOG]


def role_overview_table() -> list[dict[str, str]]:
    """Compact role → shard mapping for status dashboards."""
    return [
        {
            "agent": r.value,
            "core_purpose": AGENT_REGISTRY[r].core_purpose,
            "main_shards": ", ".join(s.value for s in AGENT_REGISTRY[r].primary_shards),
            "persona": AGENT_REGISTRY[r].persona,
            "adapter_dir": ROLE_ADAPTER_DIRS[r],
        }
        for r in AgentRole
    ]


def training_targets_for_tick(*, domain: str, tick: int) -> dict[str, Any]:
    """Suggest which agent stages should train given current tick context."""
    stage_idx = tick % 3
    stage = (AgentStage.BASE, AgentStage.SPECIALIST, AgentStage.FRONTIER)[stage_idx]
    scientist = stage_spec(AgentRole.SCIENTIST, stage)
    investor = stage_spec(AgentRole.INVESTOR, stage)
    return {
        "rotation_stage": stage.value,
        "domain": domain,
        "priority_agents": [
            {"role": AgentRole.SCIENTIST.value, "stage": stage.value, "shards": [s.value for s in scientist.shards]} if scientist else None,
            {"role": AgentRole.INVESTOR.value, "stage": stage.value, "shards": [s.value for s in investor.shards]} if investor else None,
        ],
        "train_scripts": {
            "scientist": "oss/cli/intelligence_train.py",
            "investor": "oss/cli/domain_research_train.py",
            "operator": "native/windows/train.bat",
            "governor": "oss/cli/intelligence_train.py --sources constitution",
            "builder": "oss/cli/domain_research_train.py",
        },
    }