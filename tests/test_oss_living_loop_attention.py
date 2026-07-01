"""Tests for LivingLoop attention evolution package."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


# ── Dummy substrate ───────────────────────────────────────────────────────────

class _DummySegment:
    def __init__(self, genome_id: str) -> None:
        self.genome_id = genome_id
        self.traits = {k: 0.5 for k in [
            "coding", "research", "analysis", "math",
            "curiosity", "pattern_detection", "risk_tolerance", "market_intuition",
            "finance", "strategy", "risk", "ops",
            "systems", "reliability", "safety", "ethics",
            "audit", "compliance", "design", "growth",
            "monetization", "ux", "creativity", "empathy",
            "innovation", "economics", "self_reflection", "communication",
            "reasoning", "adaptability", "leadership", "general",
        ]}

    def trait_vector(self) -> np.ndarray:
        from oss.substrate.attention_config import traits_to_vector
        return traits_to_vector(self.traits)


class _DummySubstrate:
    def segment(self, genome_id: str) -> _DummySegment:
        return _DummySegment(genome_id)


# ── KernelGenome ──────────────────────────────────────────────────────────────

def test_mutation_changes_attention_genes():
    from oss.living_loop.genome import KernelGenome
    g = KernelGenome(genome_id="test-alpha")
    orig_temp = g.temperature
    orig_tbr = g.training_binary_ratio
    orig_mg = g.max_growth
    orig_ors = g.ors_variant
    orig_int4 = g.int4_levels
    g.mutate()
    # At least some gene must change (ors_variant and int4_levels always do)
    assert (
        g.temperature != orig_temp
        or g.training_binary_ratio != orig_tbr
        or g.max_growth != orig_mg
        or g.ors_variant != orig_ors
        or g.int4_levels != orig_int4
        or g.block_size_l != 64
        or g.block_size_dh != 64
    )


def test_crossover_mixes_attention_genes():
    from oss.living_loop.genome import KernelGenome
    a = KernelGenome(genome_id="alpha", temperature=0.2, max_growth=0.1)
    b = KernelGenome(genome_id="beta",  temperature=2.0, max_growth=0.9)
    child = a.crossover(b)
    assert child.genome_id == "alpha+beta"
    assert child.temperature == pytest.approx((0.2 + 2.0) / 2.0)
    assert child.max_growth == pytest.approx((0.1 + 0.9) / 2.0)
    assert child.ors_variant in (a.ors_variant, b.ors_variant)
    assert child.int4_levels in (a.int4_levels, b.int4_levels)
    assert child.block_size_l in (a.block_size_l, b.block_size_l)


def test_crossover_child_genome_id():
    from oss.living_loop.genome import KernelGenome
    a = KernelGenome(genome_id="g1")
    b = KernelGenome(genome_id="g2")
    child = a.crossover(b)
    assert child.genome_id == "g1+g2"


def test_mutate_clamps_temperature():
    from oss.living_loop.genome import KernelGenome
    g = KernelGenome(genome_id="clamp-test", temperature=9.99)
    for _ in range(50):
        g.mutate()
        assert 0.1 <= g.temperature <= 10.0


def test_mutate_clamps_max_growth():
    from oss.living_loop.genome import KernelGenome
    g = KernelGenome(genome_id="mg-clamp", max_growth=0.0)
    for _ in range(20):
        g.mutate()
        assert 0.0 <= g.max_growth <= 2.0


# ── run_attention_experiment ──────────────────────────────────────────────────

def test_run_attention_experiment_returns_telemetry():
    from oss.living_loop.genome import KernelGenome
    from oss.living_loop.experiments import run_attention_experiment
    substrate = _DummySubstrate()
    g = KernelGenome(genome_id="test-genome")
    telemetry = run_attention_experiment(g, substrate)
    assert "mean_mag_x" in telemetry
    assert "mean_candidate_mag" in telemetry
    assert "mean_mgc_scale" in telemetry
    assert "output_norm" in telemetry
    assert telemetry["genome_id"] == "test-genome"


def test_run_attention_experiment_output_norm_positive():
    from oss.living_loop.genome import KernelGenome
    from oss.living_loop.experiments import run_attention_experiment
    g = KernelGenome(genome_id="norm-test")
    tel = run_attention_experiment(g, _DummySubstrate())
    assert tel["output_norm"] >= 0.0


def test_run_attention_experiment_ors_variants():
    from oss.living_loop.genome import KernelGenome
    from oss.living_loop.experiments import run_attention_experiment
    substrate = _DummySubstrate()
    for variant in ["qr", "identity", "random", "block_qr"]:
        g = KernelGenome(genome_id=f"ors-{variant}", ors_variant=variant)
        tel = run_attention_experiment(g, substrate)
        assert "output_norm" in tel


# ── attention_fitness ─────────────────────────────────────────────────────────

def test_attention_fitness_is_numeric():
    from oss.living_loop.fitness import attention_fitness
    from oss.living_loop.genome import KernelGenome
    from oss.living_loop.experiments import run_attention_experiment
    g = KernelGenome(genome_id="fit-genome")
    telemetry = run_attention_experiment(g, _DummySubstrate())
    score = attention_fitness(telemetry)
    assert isinstance(score, float)


def test_attention_fitness_responds_to_telemetry():
    from oss.living_loop.fitness import attention_fitness
    low  = {"mean_mgc_scale": 0.1, "mean_attn_entropy": 5.0, "output_norm": 0.0}
    high = {"mean_mgc_scale": 1.0, "mean_attn_entropy": 0.0, "output_norm": 1.0}
    assert attention_fitness(high) > attention_fitness(low)


def test_attention_fitness_mgc_dominates():
    from oss.living_loop.fitness import attention_fitness
    # High mgc_scale with no output_norm should beat zero mgc_scale with no output_norm
    a = {"mean_mgc_scale": 1.0, "mean_attn_entropy": 0.0, "output_norm": 0.0}
    b = {"mean_mgc_scale": 0.0, "mean_attn_entropy": 0.0, "output_norm": 0.0}
    assert attention_fitness(a) > attention_fitness(b)


# ── LivingLoop ────────────────────────────────────────────────────────────────

def test_living_loop_evolve_attention_updates_fitness_and_history():
    from oss.living_loop.genome import KernelGenome
    from oss.living_loop.living_loop import LivingLoop
    substrate = _DummySubstrate()
    loop = LivingLoop(substrate)
    g = KernelGenome(genome_id="loop-genome")
    loop.register_genome(g)
    loop.evolve_attention()
    assert "loop-genome" in loop.history
    assert len(loop.history["loop-genome"]) == 1
    entry = loop.history["loop-genome"][0]
    assert "fitness" in entry
    assert "telemetry" in entry


def test_living_loop_multiple_genomes():
    from oss.living_loop.genome import KernelGenome
    from oss.living_loop.living_loop import LivingLoop
    substrate = _DummySubstrate()
    loop = LivingLoop(substrate)
    for i in range(3):
        loop.register_genome(KernelGenome(genome_id=f"g{i}"))
    loop.evolve_attention()
    assert len(loop.history) == 3
    for i in range(3):
        assert len(loop.history[f"g{i}"]) == 1


def test_living_loop_fitness_accumulated_across_ticks():
    from oss.living_loop.genome import KernelGenome
    from oss.living_loop.living_loop import LivingLoop
    substrate = _DummySubstrate()
    loop = LivingLoop(substrate)
    g = KernelGenome(genome_id="multi-tick")
    loop.register_genome(g)
    loop.evolve_attention()
    loop.evolve_attention()
    assert len(loop.history["multi-tick"]) == 2
