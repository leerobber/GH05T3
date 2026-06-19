"""Concrete module breakdown — files, classes, APIs for OSS substrate."""
from __future__ import annotations

from typing import Any

MODULE_MAP: dict[str, dict[str, Any]] = {
    "genomic_substrate": {
        "path": "oss/substrate/genomic.py",
        "class": "GenomicSubstrate",
        "replaces": "filesystem modules",
        "methods": ["register(dna)", "query(capability, domain)", "segment(genome_id)"],
    },
    "species_registry": {
        "path": "oss/substrate/species_registry.py",
        "class": "SpeciesRegistry",
        "replaces": "class definitions",
        "methods": ["get_role(name)", "spawn(role, dna)", "reward_fn(role)"],
    },
    "interaction_field": {
        "path": "oss/substrate/interaction_field.py",
        "class": "InteractionField",
        "replaces": "REST/RPC APIs",
        "methods": ["publish_intent(field, agent, payload)", "collect_responses(field)", "form_swarm(intent_id)"],
    },
    "value_flow_engine": {
        "path": "oss/substrate/value_flow.py",
        "class": "ValueFlowEngine",
        "replaces": "payment/billing microservices",
        "methods": ["earn()", "create_bounty()", "list_trait()", "soul_bond()", "ddrs_reward()"],
    },
    "agent_embodiment": {
        "path": "oss/integration/embodiment.py",
        "class": "AgentEmbodiment",
        "replaces": "agent wrapper classes",
        "methods": ["perceive(event)", "act(intent)", "evolve(score)"],
    },
    "collective_mind": {
        "path": "oss/mind/omni_mind.py",
        "class": "OmniMind",
        "methods": ["sync_agents()", "assign_swarm_task()", "solve_with_swarm()", "state()"],
    },
    "economic_kernel": {
        "path": "oss/economy/",
        "classes": ["NeuroCoin", "DesireSystem"],
        "methods": ["earn/spend/transfer", "reward_agent()", "fulfill_desire()"],
    },
    "living_loop": {
        "path": "oss/integration/living_loop.py",
        "class": "LivingLoop",
        "methods": ["run_cycle(domain, tick, dry_run)", "status()"],
    },
    "species_fsm": {
        "path": "oss/ecosystem/",
        "classes": ["EcosystemState", "ecosystem_step"],
        "methods": ["species S0–S6", "omni_mind M0–M6", "omni_economy E0–E5"],
    },
    "civilization_kernel": {
        "path": "oss/kernel/",
        "classes": ["heartbeat.tick", "orchestrator_step"],
        "methods": ["kernel tick", "collaboration loop", "training schedule"],
    },
}


def module_breakdown() -> dict[str, Any]:
    return {
        "substrate_primitives": ["GenomeSegment", "SpeciesRole", "InteractionField", "ValueFlow"],
        "modules": MODULE_MAP,
        "dependency_order": [
            "genomic_substrate",
            "species_registry",
            "value_flow_engine",
            "collective_mind",
            "interaction_field",
            "living_loop",
            "species_fsm",
            "civilization_kernel",
        ],
        "v1_bridge": (
            "Wrap existing LLM + Omni-DNA + Omni-Mind + NeuroCoin; "
            "use InteractionField instead of direct API calls where possible."
        ),
    }