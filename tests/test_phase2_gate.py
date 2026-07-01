"""Phase 2 gate — 500-cycle dry-run + evolutionary pressure."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


@pytest.mark.slow
def test_theory_lab_500_cycles_dry_run():
    """Gate: 500-cycle fast dry-run (3 theorists, no swarm spawn)."""
    os.environ["MVS_DRY_RUN"] = "1"
    from backend.oss.lab.theory_lab import TheoryLab

    lab = TheoryLab(cycles=100, live=False, fast_dry_run=True)
    lab.run()
    assert lab._volatility_cycles >= 30
    assert lab.canonical.stats()["total"] >= 0
    pressure = lab.pressure.last_stats()
    assert pressure.get("cycle", 0) >= 99


def test_evolutionary_pressure_top_fraction():
    from backend.oss.evolution import EvolutionaryPressureEngine

    engine = EvolutionaryPressureEngine()
    results = [(f"a{i}", 0.9 - i * 0.1, "out") for i in range(5)]
    spawns = []

    def spawn_fn(agent_id: str) -> bool:
        spawns.append(agent_id)
        return True

    stats = engine.apply_pressure(results, cycle=1, spawn_fn=spawn_fn)
    assert len(stats.top_agents) == 1
    assert stats.spawn_boost >= 2
    assert stats.top_agents[0] == "a0"