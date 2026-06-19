"""Civilization Kernel data shards — typed knowledge territories per agent role."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ShardType(str, Enum):
    """Canonical shard families used across agent stages."""

    # Base
    WORLD_MODEL = "world_model"
    CODE = "code"
    MARKETS = "markets"
    OPERATIONS = "operations"
    AGENCY_TOOLS = "agency_tools"
    GOVERNANCE = "governance"

    # Specialist
    SCIENTIFIC_TEXT = "scientific_text"
    SIMULATION = "simulation"
    ADVANCED_MARKETS = "advanced_markets"
    ON_CHAIN = "on_chain"
    RISK = "risk"
    ADVANCED_OPERATIONS = "advanced_operations"
    SECURITY = "security"
    LEGAL = "legal"

    # Frontier
    FRONTIER_SIMULATION = "frontier_simulation"
    META_SCIENCE = "meta_science"
    MACRO_STRATEGY = "macro_strategy"
    CROSS_ROLE = "cross_role"
    META_ALIGNMENT = "meta_alignment"


@dataclass(frozen=True)
class ShardSpec:
    """One shard bucket: data types, ingest hints, and adapter target."""

    key: ShardType
    title: str
    data_types: tuple[str, ...]
    ingest_paths: tuple[str, ...] = ()
    adapter_dir: str = "gh05t3_lora_adapter"
    forge_domain: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key.value,
            "title": self.title,
            "data_types": list(self.data_types),
            "ingest_paths": list(self.ingest_paths),
            "adapter_dir": self.adapter_dir,
            "forge_domain": self.forge_domain,
        }


# Role overview — primary shards each agent draws from at all stages
ROLE_PRIMARY_SHARDS: dict[str, tuple[ShardType, ...]] = {
    "scientist": (ShardType.WORLD_MODEL, ShardType.SIMULATION, ShardType.GOVERNANCE),
    "investor": (ShardType.MARKETS, ShardType.WORLD_MODEL, ShardType.GOVERNANCE),
    "operator": (ShardType.AGENCY_TOOLS, ShardType.OPERATIONS, ShardType.GOVERNANCE),
    "governor": (ShardType.GOVERNANCE, ShardType.WORLD_MODEL, ShardType.MARKETS),
    "builder": (ShardType.OPERATIONS, ShardType.AGENCY_TOOLS, ShardType.MARKETS),
}


SHARD_CATALOG: dict[ShardType, ShardSpec] = {
    ShardType.WORLD_MODEL: ShardSpec(
        ShardType.WORLD_MODEL,
        "World-model",
        ("general text", "textbooks", "intro articles", "social/legal/cultural knowledge"),
        ("backend/data/training/", "training_data/"),
        "gh05t3_lora_adapter",
        "general_cognition",
    ),
    ShardType.CODE: ShardSpec(
        ShardType.CODE,
        "Code",
        ("Python repos", "notebooks", "math/physics libraries", "CI configs"),
        ("backend/", "oss/"),
        "code_adapter",
        "computational_science",
    ),
    ShardType.MARKETS: ShardSpec(
        ShardType.MARKETS,
        "Markets",
        ("price series", "macro indicators", "demand signals", "pricing pages"),
        ("data/spin_dataset.jsonl", "training_data/domain_research/"),
        "domain_research_adapter",
        "mycological_network_economics",
    ),
    ShardType.OPERATIONS: ShardSpec(
        ShardType.OPERATIONS,
        "Operations",
        ("SaaS patterns", "deployment configs", "product analytics", "funnels"),
        ("training_data/domain_research/",),
        "ops_adapter",
        "systems_engineering",
    ),
    ShardType.AGENCY_TOOLS: ShardSpec(
        ShardType.AGENCY_TOOLS,
        "Agency/Tools",
        ("tool-use traces", "API docs", "multi-step workflows", "integration guides"),
        ("backend/site_agents/", "mcps/"),
        "ops_adapter",
        "agentic_systems_science",
    ),
    ShardType.GOVERNANCE: ShardSpec(
        ShardType.GOVERNANCE,
        "Governance",
        ("policies", "ethics", "risk frameworks", "compliance guidelines"),
        ("oss/train/constitution.py",),
        "security_adapter",
        "alignment_and_safety_science",
    ),
    ShardType.SCIENTIFIC_TEXT: ShardSpec(
        ShardType.SCIENTIFIC_TEXT,
        "Scientific text",
        ("research papers", "abstracts", "citations", "protocols"),
        ("backend/data/training/forge_elite_strands.jsonl",),
        "research_adapter",
        "epistemology_and_discovery",
    ),
    ShardType.SIMULATION: ShardSpec(
        ShardType.SIMULATION,
        "Simulation",
        ("ODE/PDE outputs", "climate models", "molecular runs", "parameters + outputs"),
        (),
        "research_adapter",
        "computational_science",
    ),
    ShardType.ADVANCED_MARKETS: ShardSpec(
        ShardType.ADVANCED_MARKETS,
        "Advanced markets",
        ("tick data", "order books", "volatility", "liquidity metrics"),
        ("data/spin_dataset.jsonl",),
        "domain_research_adapter",
        "statistical_inference_science",
    ),
    ShardType.ON_CHAIN: ShardSpec(
        ShardType.ON_CHAIN,
        "On-chain",
        ("transactions", "DeFi pools", "governance votes", "token flows"),
        (),
        "domain_research_adapter",
        "mycological_network_economics",
    ),
    ShardType.RISK: ShardSpec(
        ShardType.RISK,
        "Risk",
        ("stress scenarios", "drawdowns", "tail events", "regime shifts"),
        (),
        "security_adapter",
        "statistical_inference_science",
    ),
    ShardType.ADVANCED_OPERATIONS: ShardSpec(
        ShardType.ADVANCED_OPERATIONS,
        "Advanced operations",
        ("K8s configs", "distributed logs", "incident reports", "postmortems"),
        ("backend/",),
        "ops_adapter",
        "systems_engineering",
    ),
    ShardType.SECURITY: ShardSpec(
        ShardType.SECURITY,
        "Security",
        ("auth policies", "threat models", "security playbooks"),
        ("backend/security/",),
        "security_adapter",
        "cyber_defense_science",
    ),
    ShardType.LEGAL: ShardSpec(
        ShardType.LEGAL,
        "Legal",
        ("statutes", "regulations", "case summaries", "charters"),
        ("training_data/domain_research/",),
        "security_adapter",
        "alignment_and_safety_science",
    ),
    ShardType.FRONTIER_SIMULATION: ShardSpec(
        ShardType.FRONTIER_SIMULATION,
        "Frontier simulation",
        ("spatiotemporal systems", "chaotic models", "multi-scale coupled runs"),
        (),
        "research_adapter",
        "theoretical_physics_and_complexity",
    ),
    ShardType.META_SCIENCE: ShardSpec(
        ShardType.META_SCIENCE,
        "Meta-science",
        ("methodology", "systematic reviews", "research design guidelines"),
        ("backend/data/training/forge_elite_strands.jsonl",),
        "research_adapter",
        "epistemology_and_discovery",
    ),
    ShardType.MACRO_STRATEGY: ShardSpec(
        ShardType.MACRO_STRATEGY,
        "Macro-strategy",
        ("multi-asset portfolios", "factor models", "scenario analyses"),
        ("training_data/domain_research/sovereign_nation.jsonl",),
        "domain_research_adapter",
        "statistical_inference_science",
    ),
    ShardType.CROSS_ROLE: ShardSpec(
        ShardType.CROSS_ROLE,
        "Cross-role",
        ("multi-agent workflows", "dependency graphs", "ecosystem maps"),
        ("data/kernel_ticks.jsonl",),
        "gh05t3_lora_adapter",
        "agentic_systems_science",
    ),
    ShardType.META_ALIGNMENT: ShardSpec(
        ShardType.META_ALIGNMENT,
        "Meta-alignment",
        ("alignment research", "constitutional AI", "incident mitigations"),
        ("oss/train/constitution.py",),
        "security_adapter",
        "alignment_and_safety_science",
    ),
}


def list_shards() -> list[dict[str, Any]]:
    return [s.to_dict() for s in SHARD_CATALOG.values()]


def shard_for_key(key: str) -> ShardSpec | None:
    try:
        return SHARD_CATALOG[ShardType(key)]
    except (KeyError, ValueError):
        return None


def primary_shards_for_role(role: str) -> list[dict[str, Any]]:
    keys = ROLE_PRIMARY_SHARDS.get(role, ())
    return [SHARD_CATALOG[k].to_dict() for k in keys if k in SHARD_CATALOG]