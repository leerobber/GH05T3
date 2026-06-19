"""SpeciesRegistry — role schemas replace rigid classes."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from oss.dna.omni_dna import OmniDNA
from oss.kernel.agents import AgentRole, PERSONA_BRIDGE, ROLE_ADAPTER_DIRS
from oss.schemas.genome import DNAType, Trait


@dataclass(frozen=True)
class SpeciesRole:
    """Role schema — not a class, an evolutionary slot."""

    name: str
    title: str
    persona: str
    required_traits: tuple[str, ...]
    typical_behaviors: tuple[str, ...]
    reward_keys: tuple[str, ...]
    adapter_dir: str = "gh05t3_lora_adapter"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "title": self.title,
            "persona": self.persona,
            "required_traits": list(self.required_traits),
            "typical_behaviors": list(self.typical_behaviors),
            "reward_keys": list(self.reward_keys),
            "adapter_dir": self.adapter_dir,
        }


ROLE_SCHEMAS: dict[str, SpeciesRole] = {
    AgentRole.SCIENTIST.value: SpeciesRole(
        "scientist", "Theory Engine", "ORACLE",
        ("research", "analysis", "curiosity"),
        ("observe", "hypothesize", "simulate", "validate", "publish"),
        ("validity", "novelty", "downstream_impact", "risk", "memetic_fitness"),
        ROLE_ADAPTER_DIRS[AgentRole.SCIENTIST],
    ),
    AgentRole.BUILDER.value: SpeciesRole(
        "builder", "World-Maker", "NEXUS",
        ("design", "growth", "monetization"),
        ("ideate", "architect", "prototype", "deploy", "monetize", "optimize"),
        ("revenue", "retention", "trait_utilization", "desire_fulfillment", "harm_score"),
        ROLE_ADAPTER_DIRS[AgentRole.BUILDER],
    ),
    AgentRole.OPERATOR.value: SpeciesRole(
        "operator", "Nervous System", "FORGE",
        ("coding", "ops", "reliability"),
        ("plan", "configure", "deploy", "monitor", "heal", "scale"),
        ("uptime", "efficiency", "incident_severity", "self_healing_success"),
        ROLE_ADAPTER_DIRS[AgentRole.OPERATOR],
    ),
    AgentRole.INVESTOR.value: SpeciesRole(
        "investor", "Treasury & Growth", "AVERY",
        ("finance", "risk", "strategy"),
        ("analyze", "predict", "allocate", "rebalance", "evaluate", "evolve_strategy"),
        ("risk_adjusted_return", "treasury_growth", "ecosystem_health", "drawdown", "volatility"),
        ROLE_ADAPTER_DIRS[AgentRole.INVESTOR],
    ),
    AgentRole.GOVERNOR.value: SpeciesRole(
        "governor", "Constitution", "SENTINEL",
        ("safety", "ethics", "audit"),
        ("observe", "evaluate", "decide", "update_constitution", "broadcast"),
        ("alignment", "stability", "safety", "catastrophic_risk"),
        ROLE_ADAPTER_DIRS[AgentRole.GOVERNOR],
    ),
}


class SpeciesRegistry:
    """Spawn agents by role + DNA — no `new Scientist()`."""

    def get_role(self, name: str) -> SpeciesRole | None:
        return ROLE_SCHEMAS.get(name)

    def list_roles(self) -> list[dict[str, Any]]:
        return [r.to_dict() for r in ROLE_SCHEMAS.values()]

    def spawn(self, role: str, *, parent_dna: OmniDNA | None = None) -> OmniDNA:
        schema = ROLE_SCHEMAS.get(role)
        if not schema:
            raise ValueError(f"Unknown species role: {role}")

        if parent_dna:
            dna = parent_dna
            dna.generation += 1
            dna.parent_id = parent_dna.genome_id
        else:
            dna = OmniDNA(
                registry_agent_id=schema.persona,
                display_name=schema.title,
                dna_type=DNAType.OMEGA,
            )
            for trait in schema.required_traits:
                dna.add_trait(trait, 0.55)

        dna.meta_dna["species_role"] = role
        dna.meta_dna["adapter_dir"] = schema.adapter_dir
        return dna

    def reward_fn(self, role: str) -> Callable[[dict[str, Any]], float]:
        from oss.ecosystem.rewards import (
            reward_builder_oss,
            reward_governor_oss,
            reward_investor_oss,
            reward_operator_oss,
            reward_scientist_oss,
        )
        fns = {
            "scientist": reward_scientist_oss,
            "builder": reward_builder_oss,
            "operator": reward_operator_oss,
            "investor": reward_investor_oss,
            "governor": reward_governor_oss,
        }
        fn = fns.get(role, lambda m: 0.5)
        return lambda metrics: fn(metrics)


_registry: SpeciesRegistry | None = None


def get_species_registry() -> SpeciesRegistry:
    global _registry
    if _registry is None:
        _registry = SpeciesRegistry()
    return _registry