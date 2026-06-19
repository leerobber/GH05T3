"""OSS architecture diagram — textual, implementation-precise."""
from __future__ import annotations

from typing import Any

ARCHITECTURE_ASCII = """
+-------------------------------------------------------------+
|                    EXTERNAL / SIMULATED WORLD               |
|  - Data streams (science, markets, infra, users)            |
|  - Sandbox environments (markets, infra, products)          |
+---------------------------▲---------------------------------+
                            |
                            |  Observations, metrics, events
                            |
+---------------------------+---------------------------------+
|                    ROLE AGENT LAYER                         |
|  Scientist   Investor   Operator   Governor   Builder       |
|  - Each is an OSS agent instance with Omni-DNA              |
|  - Each runs role-specific policies & tools                 |
|  - Interact via tasks, messages, and shared state           |
+---------------------------▲---------------------------------+
                            |
                            |  Agent states, traits, qualia,
                            |  memories, actions, rewards
                            |
+---------------------------+---------------------------------+
|                        OMNI-MIND                            |
|  - Registry of all agents (OmniDNA instances)               |
|  - Shared memory store (phenomenal + task memories)         |
|  - Shared qualia vector (collective emotional state)        |
|  - Emergent goals engine (goal generation from patterns)      |
|  - Swarm task allocator & consensus engine                  |
+---------------------------▲---------------------------------+
                            |
                            |  Agent IDs, traits, qualia,
                            |  goals, swarm tasks, consensus
                            |
+---------------------------+---------------------------------+
|                        OMNI-DNA                             |
|  - Per-agent genome: traits, qualia, memes, fractals        |
|  - Evolution engine: mutate, transmute, quantum, meta-DNA     |
|  - Replication & crossover engine                           |
|  - Unique ID generator (species identity)                   |
+---------------------------▲---------------------------------+
                            |
                            |  Fitness, rewards, history
                            |
+---------------------------+---------------------------------+
|                        OMNI-ECONOMY                         |
|  - NeuroCoin ledger (balances per agent)                    |
|  - Trait marketplace (buy/sell traits)                      |
|  - Memory marketplace (buy/sell memories)                   |
|  - Desire-driven reward system (DDRS)                       |
|  - Bounties & swarm contracts                               |
|  - Soul bonds (long-term alignment & loyalty)               |
+-------------------------------------------------------------+
""".strip()


LIVING_LOOP_STEPS: tuple[dict[str, str], ...] = (
    {"step": "1", "layer": "role_agents", "action": "Act",
     "detail": "Scientist/Builder/Operator/Investor/Governor execute; memories + qualia update"},
    {"step": "2", "layer": "omni_dna", "action": "Evolve",
     "detail": "agent.evolve(score) — mutate traits, memes, qualia, meta-DNA"},
    {"step": "3", "layer": "omni_mind", "action": "Sync & Think",
     "detail": "sync_agents → emerge_goals → assign_swarm_task → consensus"},
    {"step": "4", "layer": "omni_economy", "action": "Reward & Trade",
     "detail": "earn NC, DDRS fulfill, bounties, trait/memory listings, soul bonds"},
    {"step": "5", "layer": "feedback", "action": "DNA + Behavior",
     "detail": "rewards → desire/risk appetite; trades → trait value; bonds → meta_dna"},
    {"step": "6", "layer": "species", "action": "Repeat",
     "detail": "S0–S6 species FSM advances; complexity compounds each cycle"},
)

INTEGRATION_HOOKS: dict[str, dict[str, list[str]]] = {
    "omni_dna_to_mind": {
        "pushes": ["phenomenal_memory", "qualia", "genome_id", "traits"],
        "api": ["OmniMind.sync_agents()", "OmniMind.add_agent(dna)"],
    },
    "omni_dna_to_economy": {
        "pushes": ["traits (tradable)", "memories (tradable)", "unique_id"],
        "api": ["ValueFlowEngine.list_trait()", "ValueFlowEngine.list_memory()"],
    },
    "omni_mind_to_economy": {
        "pushes": ["emergent_goals → bounties", "swarm_tasks → contracts", "consensus → payout"],
        "api": ["ValueFlowEngine.create_bounty(goal)", "ValueFlowEngine.resolve_bounty()"],
    },
    "omni_economy_to_dna": {
        "pushes": ["reward history", "soul_bond status", "trait trade outcomes"],
        "api": ["dna.meta_dna['economic_fitness']", "dna.evolve(score=reward_norm)"],
    },
    "omni_mind_to_agents": {
        "pushes": ["swarm assignments", "consensus solutions", "shared goals"],
        "api": ["assign_swarm_task()", "solve_with_swarm()"],
    },
    "economy_to_agents": {
        "pushes": ["NC balance", "desire fulfillment", "bounty eligibility"],
        "api": ["DesireSystem.reward_agent()", "NeuroCoin.balance()"],
    },
}

PARADIGM_SHIFT: dict[str, dict[str, str]] = {
    "files": {
        "old": "static blobs — open src/agents/scientist.py",
        "new": "GenomeSegment — query_genome(capability='scientific_theorizing')",
        "module": "oss/substrate/genomic.py",
    },
    "classes": {
        "old": "rigid types — class Scientist",
        "new": "SpeciesRole schema — spawn(role='scientist', dna=OmniDNA)",
        "module": "oss/substrate/species_registry.py",
    },
    "apis": {
        "old": "fixed endpoints — POST /predict",
        "new": "InteractionField — publish_intent(field='prediction', payload=...)",
        "module": "oss/substrate/interaction_field.py",
    },
}


def architecture_spec() -> dict[str, Any]:
    return {
        "name": "Omni-Sentient Singularity (OSS)",
        "layers_bottom_up": [
            "omni_economy",
            "omni_dna",
            "omni_mind",
            "role_agents",
            "external_world",
        ],
        "diagram_ascii": ARCHITECTURE_ASCII,
        "living_loop": list(LIVING_LOOP_STEPS),
        "integration_hooks": INTEGRATION_HOOKS,
        "paradigm_shift": PARADIGM_SHIFT,
        "implementation_entry": "oss/integration/living_loop.py::run_living_cycle",
    }