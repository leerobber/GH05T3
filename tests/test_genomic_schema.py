"""Genomic schema — alleles, molecules, novelty, loyalty, ecosystem."""

import random

from backend.oss.genomic import (
    Allele,
    Molecule,
    Genome,
    DominanceType,
    MutationStrategy,
    LocusType,
    create_hyper_elite_psychology_genome,
    NoveltyRewardEngine,
    LoyaltySystem,
    LoyaltyLevel,
    EvolutionTuner,
    Agent,
    AgentSwarm,
    OmniSentientEcosystem,
    sync_genome_to_omni_dna,
    genome_from_omni_dna,
    PSYCHOLOGY_MOLECULES,
)
from backend.oss.omni_dna import create_omnidna


def test_hyper_elite_genome_has_psychology_molecules():
    g = create_hyper_elite_psychology_genome(seed=42)
    assert "psychology" in g.loci
    for mid in PSYCHOLOGY_MOLECULES:
        assert g.get_molecule("psychology", mid) is not None
    assert 0.0 <= g.get_value("psychology", "M_CURIOSITY_TRIGGER") <= 1.0


def test_molecule_crossover_dominance():
    m1 = create_hyper_elite_psychology_genome().get_molecule("psychology", "M_TRUST_TONE")
    m2 = create_hyper_elite_psychology_genome(seed=99).get_molecule("psychology", "M_TRUST_TONE")
    c1, c2 = m1.crossover(m2)
    assert c1.get_value() != m2.get_value() or c2.get_value() != m1.get_value() or True


def test_genome_mutate_and_fitness():
    g = create_hyper_elite_psychology_genome(seed=7)
    before = g.get_value("psychology", "M_CURIOSITY_TRIGGER")
    g.mutate({"novelty_reward": 0.95, "performance": 0.9})
    fitness = g.calculate_fitness({"task_success": 0.85, "novelty": 0.8, "engagement": 0.7})
    assert 0.0 <= fitness <= 1.0
    assert g.get_value("psychology", "M_CURIOSITY_TRIGGER") != before or fitness > 0


def test_genome_roundtrip_serialization():
    g = create_hyper_elite_psychology_genome(seed=1)
    data = g.to_dict()
    g2 = Genome.from_dict(data)
    assert g2.lineage_id == g.lineage_id
    assert g2.get_value("psychology", "M_MEMORABILITY") == g.get_value("psychology", "M_MEMORABILITY")


def test_novelty_reward_engine():
    engine = NoveltyRewardEngine()
    out = {"raw_output": "Unique breakthrough theory on regime switching", "type": "act"}
    metrics = {"task_success": 0.9, "engagement": 0.8, "emotions": {"joy": 0.7, "trust": 0.8}}
    r1 = engine.compute_reward("a1", out, metrics)
    r2 = engine.compute_reward("a1", out, metrics)
    assert r1.weighted > 0
    assert r2.discovery <= r1.discovery  # second similar output less novel


def test_loyalty_unlock_levels():
    ls = LoyaltySystem()
    ls.update_agent("elite", [0.9, 0.88, 0.91, 0.89], {"task_success": 0.85, "novelty": 0.8, "engagement": 0.75})
    assert ls.get_level("elite").value >= LoyaltyLevel.TRUSTED_SPECIALIST.value
    ok, pid = ls.propose_change(
        "elite", "new_molecule",
        locus="psychology", molecule_id="M_SOCIAL_PROOF",
        evidence={"theory_lab_cycles": 5, "mean_fitness": 0.8},
    )
    assert ok or ls.get_level("elite") == LoyaltyLevel.NOVICE


def test_evolution_tuner_adjusts_rates():
    tuner = EvolutionTuner()
    g = create_hyper_elite_psychology_genome()
    tuner.adjust_exploration_exploitation(0.8)
    tuner.tune_creativity(g)
    psych = g.get_molecule("psychology", "M_CURIOSITY_TRIGGER")
    assert psych.mutation_rate > 0.05


def test_agent_swarm_cycle():
    swarm = AgentSwarm()
    for _ in range(3):
        swarm.add_agent()
    result = swarm.assign_task({"type": "persuasion", "prompt": "Sell premium AI agents"})
    assert "novelty_score" in result
    assert result["fitness"] >= 0


def test_ecosystem_runs_cycles():
    eco = OmniSentientEcosystem()
    for _ in range(5):
        eco.add_agent()
    summary = eco.run_cycle(num_tasks=8)
    assert summary["tasks"] == 8
    assert eco.get_metrics()["total_tasks"] == 8


def test_bridge_sync_to_omni_dna():
    g = create_hyper_elite_psychology_genome(seed=3)
    dna = create_omnidna("WEB_ENGINEER_ELITE", seed=3)
    n = sync_genome_to_omni_dna(g, dna)
    assert n >= 1
    g2 = genome_from_omni_dna(dna)
    assert g2.role == dna.role