"""Theory Lab ↔ VolatilityWorld integration — Phase 2 Week 4."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def test_world_weights_volatility_at_least_40_percent():
    from backend.oss.lab.theory_lab import _WORLD_WEIGHTS

    weights = dict(_WORLD_WEIGHTS)
    assert weights["volatility"] >= 0.40
    assert abs(sum(weights.values()) - 1.0) < 0.01


def test_volatility_challenge_task_structure():
    from backend.oss.lab.theory_lab import TheoryLab
    from backend.oss.world.volatility_world import VolatilityWorld

    lab = TheoryLab(cycles=1, live=False)
    world = VolatilityWorld(length=100, seed=1)
    task = lab._volatility_challenge_task(world)
    assert "prompt" in task
    assert task.get("world_type") == "volatility"
    assert "series_id" in task["world_data"]
    assert "challenge" in task


def test_evaluate_volatility_v1_returns_weighted_score():
    from backend.oss.lab.theory_lab import TheoryLab
    from backend.oss.world.volatility_world import VolatilityWorld

    lab = TheoryLab(cycles=1, live=False)
    world = VolatilityWorld(length=80, seed=3)
    task = lab._volatility_challenge_task(world)
    output = (
        "Regime-switching stochastic volatility model with Markov transitions "
        "between low and high volatility states. Distribution and heteroskedastic clustering."
    )
    result = lab._evaluate_volatility_v1(world, "theorist_test", output, task)
    assert "weighted_score" in result
    assert result["weighted_score"] > 0.3


@pytest.mark.anyio
async def test_ecosystem_volatility_pressure_cycle():
    from backend.oss.genomic.ecosystem import OmniSentientEcosystem
    from backend.oss.genomic.agents import Agent
    from backend.oss.genomic.hyper_elite import create_hyper_elite_psychology_genome

    eco = OmniSentientEcosystem()
    eco.register(Agent(agent_id="oracle", genome=create_hyper_elite_psychology_genome("oracle"), role="oracle"))
    result = await eco.run_cycle(pressure_type="volatility")
    assert result["pressure_type"] == "volatility"
    assert result["agents"][0]["fitness"] > 0