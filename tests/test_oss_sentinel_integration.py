"""Integration tests for SentinelPrime + LivingLoop + DeployManager + MetaScheduler."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


# ── Shared dummy substrate ────────────────────────────────────────────────────

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


# ── SentinelPrime unit ────────────────────────────────────────────────────────

def test_sentinel_score_genome_returns_genome_scores():
    from oss.governance.sentinel_prime import SentinelPrime
    s = SentinelPrime()
    tel = {"mean_mgc_scale": 0.9, "mean_attn_entropy": 0.1, "trait_alignment": 0.8}
    scores = s.score_genome("g1", tel)
    assert 0.0 <= scores.loyalty <= 1.0
    assert 0.0 <= scores.intelligence <= 1.0


def test_sentinel_decide_retired_with_no_history():
    from oss.governance.sentinel_prime import SentinelPrime
    s = SentinelPrime()
    assert s.decide("unknown-genome") == "retired"


def test_sentinel_decide_returns_valid_status():
    from oss.governance.sentinel_prime import SentinelPrime
    s = SentinelPrime()
    tel = {"mean_mgc_scale": 0.5, "mean_attn_entropy": 0.5}
    scores = s.score_genome("g1", tel)
    s.record("g1", scores)
    assert s.decide("g1") in ("active", "canary", "retired")


def test_sentinel_consistency_window_trims():
    from oss.governance.sentinel_prime import SentinelPrime
    s = SentinelPrime(consistency_window=3)
    tel = {"mean_mgc_scale": 0.5}
    for _ in range(10):
        s.record("g1", s.score_genome("g1", tel))
    assert len(s.history["g1"]) == 3


def test_sentinel_elite_genome_becomes_active():
    from oss.governance.sentinel_prime import SentinelPrime, GenomeScores
    s = SentinelPrime(consistency_window=2)
    elite = GenomeScores(
        loyalty=0.9, intelligence=0.85, innovation=0.8,
        genetic_quality=0.85, resilience=0.75, long_horizon=0.8,
    )
    s.record("elite", elite)
    s.record("elite", elite)
    assert s.decide("elite") == "active"


def test_sentinel_mid_tier_genome_is_canary():
    from oss.governance.sentinel_prime import SentinelPrime, GenomeScores
    s = SentinelPrime(consistency_window=2)
    mid = GenomeScores(
        loyalty=0.65, intelligence=0.60, innovation=0.55,
        genetic_quality=0.65, resilience=0.4, long_horizon=0.4,
    )
    s.record("mid", mid)
    s.record("mid", mid)
    assert s.decide("mid") == "canary"


def test_sentinel_status_summary():
    from oss.governance.sentinel_prime import SentinelPrime
    s = SentinelPrime()
    tel = {}
    s.record("a", s.score_genome("a", tel))
    s.record("b", s.score_genome("b", tel))
    summary = s.status_summary()
    assert set(summary.keys()) == {"a", "b"}
    assert all(v in ("active", "canary", "retired") for v in summary.values())


# ── NarrativeTrace unit ───────────────────────────────────────────────────────

def test_narrative_trace_log_and_retrieve():
    from oss.governance.narrative_trace import NarrativeTrace
    t = NarrativeTrace()
    t.log("deployment_decision", genome_id="g1", status="canary", fitness=0.7)
    assert len(t.events) == 1
    assert t.events[0].action == "deployment_decision"
    assert t.events[0].genome_id == "g1"
    assert t.events[0].details["status"] == "canary"


def test_narrative_trace_epoch_increments():
    from oss.governance.narrative_trace import NarrativeTrace
    t = NarrativeTrace()
    t.log("tick_start")
    t.next_epoch()
    t.log("tick_start")
    assert t.events[0].epoch == 0
    assert t.events[1].epoch == 1


def test_narrative_trace_filter_by_action():
    from oss.governance.narrative_trace import NarrativeTrace
    t = NarrativeTrace()
    t.log("deploy", genome_id="g1")
    t.log("retire", genome_id="g2")
    t.log("deploy", genome_id="g3")
    deploys = t.filter(action="deploy")
    assert len(deploys) == 2


def test_narrative_trace_to_dict():
    from oss.governance.narrative_trace import NarrativeTrace
    t = NarrativeTrace()
    t.log("test_event", genome_id="g0", val=42)
    d = t.to_dict()
    assert "events" in d
    assert d["events"][0]["action"] == "test_event"


# ── ObjectiveRouter unit ──────────────────────────────────────────────────────

def test_objective_router_default():
    from oss.goals.objective_router import ObjectiveRouter
    r = ObjectiveRouter()
    assert r.get_objective() == "stability"


def test_objective_router_set_and_get():
    from oss.goals.objective_router import ObjectiveRouter
    r = ObjectiveRouter()
    r.set_objective("exploration")
    assert r.get_objective() == "exploration"


def test_objective_router_invalid_raises():
    from oss.goals.objective_router import ObjectiveRouter
    r = ObjectiveRouter()
    with pytest.raises(ValueError):
        r.set_objective("world_domination")


# ── DeployManager integration ─────────────────────────────────────────────────

def test_deploy_manager_sync_and_summary():
    from oss.living_loop.genome import KernelGenome
    from oss.living_loop.living_loop import LivingLoop
    from oss.runtime.deploy_manager import DeployManager

    sub = _DummySubstrate()
    loop = LivingLoop(sub)
    for i in range(3):
        loop.register_genome(KernelGenome(genome_id=f"dm-{i}"))
    loop.evolve_attention()

    dm = DeployManager(sentinel=loop.sentinel)
    dm.sync_from_living_loop(loop)

    summary = dm.summary()
    total = sum(len(v) for v in summary.values())
    assert total == 3


def test_deploy_manager_select_active_returns_none_or_str():
    from oss.living_loop.genome import KernelGenome
    from oss.living_loop.living_loop import LivingLoop
    from oss.runtime.deploy_manager import DeployManager

    sub = _DummySubstrate()
    loop = LivingLoop(sub)
    loop.register_genome(KernelGenome(genome_id="active-test"))
    loop.evolve_attention()

    dm = DeployManager(sentinel=loop.sentinel)
    dm.sync_from_living_loop(loop)
    result = dm.select_active_genome()
    assert result is None or isinstance(result, str)


# ── LivingLoop + SentinelPrime integration ────────────────────────────────────

def test_sentinel_prime_drives_deployment_status():
    from oss.living_loop.genome import KernelGenome
    from oss.living_loop.living_loop import LivingLoop

    loop = LivingLoop(substrate=_DummySubstrate())
    g = KernelGenome(genome_id="g1")
    loop.register_genome(g)

    for _ in range(5):
        loop.evolve_attention()

    status = loop.sentinel.decide("g1")
    assert status in ("active", "canary", "retired")


def test_living_loop_telemetry_has_deployment_status():
    from oss.living_loop.genome import KernelGenome
    from oss.living_loop.living_loop import LivingLoop

    loop = LivingLoop(substrate=_DummySubstrate())
    g = KernelGenome(genome_id="status-g")
    loop.register_genome(g)
    loop.evolve_attention()

    last = loop.history["status-g"][-1]
    assert "deployment_status" in last["telemetry"]
    assert last["telemetry"]["deployment_status"] in ("active", "canary", "retired")


def test_living_loop_sentinel_history_grows():
    from oss.living_loop.genome import KernelGenome
    from oss.living_loop.living_loop import LivingLoop

    loop = LivingLoop(substrate=_DummySubstrate())
    g = KernelGenome(genome_id="hist-g")
    loop.register_genome(g)

    for _ in range(3):
        loop.evolve_attention()

    assert len(loop.sentinel.history.get("hist-g", [])) <= loop.sentinel.consistency_window
    assert len(loop.sentinel.history.get("hist-g", [])) >= 1


# ── MetaScheduler integration ─────────────────────────────────────────────────

def test_meta_scheduler_run_epoch_returns_summary():
    from oss.living_loop.genome import KernelGenome
    from oss.living_loop.living_loop import LivingLoop
    from oss.governance.meta_scheduler import MetaScheduler, ScheduleConfig
    from oss.goals.objective_router import ObjectiveRouter

    sub = _DummySubstrate()
    loop = LivingLoop(sub)
    loop.register_genome(KernelGenome(genome_id="sched-g"))

    sched = MetaScheduler(
        loop=loop,
        sentinel=loop.sentinel,
        objectives=ObjectiveRouter(),
        config=ScheduleConfig(max_cycles_per_epoch=2),
    )
    result = sched.run_epoch("stability")
    assert "objective" in result
    assert "best_fitness" in result
    assert "mean_fitness" in result
    assert "stalled" in result
    assert "sentinel_decisions" in result


def test_meta_scheduler_switches_to_exploration_when_stalled():
    from oss.living_loop.genome import KernelGenome
    from oss.living_loop.living_loop import LivingLoop
    from oss.governance.meta_scheduler import MetaScheduler, ScheduleConfig
    from oss.goals.objective_router import ObjectiveRouter

    sub = _DummySubstrate()
    loop = LivingLoop(sub)
    loop.register_genome(KernelGenome(genome_id="stall-g"))

    objectives = ObjectiveRouter()
    sched = MetaScheduler(
        loop=loop,
        sentinel=loop.sentinel,
        objectives=objectives,
        config=ScheduleConfig(max_cycles_per_epoch=1, min_fitness_delta=999.0),
    )
    # First epoch sets baseline
    sched.run_epoch("exploitation")
    # Second epoch — delta < min_fitness_delta → switches to "exploration"
    result = sched.run_epoch("exploitation")
    assert result["stalled"] is True
    assert objectives.get_objective() == "exploration"


def test_meta_scheduler_multiple_genomes():
    from oss.living_loop.genome import KernelGenome
    from oss.living_loop.living_loop import LivingLoop
    from oss.governance.meta_scheduler import MetaScheduler, ScheduleConfig
    from oss.goals.objective_router import ObjectiveRouter

    sub = _DummySubstrate()
    loop = LivingLoop(sub)
    for i in range(4):
        loop.register_genome(KernelGenome(genome_id=f"ms-{i}"))

    sched = MetaScheduler(
        loop=loop,
        sentinel=loop.sentinel,
        objectives=ObjectiveRouter(),
        config=ScheduleConfig(max_cycles_per_epoch=2),
    )
    result = sched.run_epoch("sharpness")
    assert len(result["sentinel_decisions"]) == 4
