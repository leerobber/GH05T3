"""Real divergence measurement and pressure-driven speciation."""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "backend"))

from backend.oss.speciation import SpeciationEngine


def _make_engine() -> SpeciationEngine:
    engine = SpeciationEngine(divergence_threshold=0.10)
    engine.species.clear()
    engine.events.clear()
    return engine


def test_measure_group_divergence_increases_with_pressure():
    from backend.oss.mvs import get_mvs, create_omnidna

    engine = _make_engine()
    sub = get_mvs()["substrate"]

    ids = []
    for i in range(4):
        dna = create_omnidna("THEORIST_ELITE", seed=100 + i)
        gid = sub.register_genome(dna, role="THEORIST_ELITE")
        ids.append(gid)

    before = engine.measure_group_divergence(ids)
    engine.apply_divergence_pressure(ids, strength=0.15)
    after = engine.measure_group_divergence(ids)

    assert after > before


def test_attempt_speciation_with_pressure_returns_measured_divergence():
    from backend.oss.mvs import get_mvs, create_omnidna

    engine = _make_engine()
    sub = get_mvs()["substrate"]

    ids = []
    for i in range(5):
        dna = create_omnidna("THEORIST_ELITE", seed=200 + i)
        gid = sub.register_genome(dna, role="THEORIST_ELITE")
        ids.append(gid)

    new_sp, measured = engine.attempt_speciation_with_pressure(
        ids, current_cycle=1, niche="test", base_strength=0.12, max_rounds=10
    )

    assert measured >= 0.0
    if new_sp:
        assert engine.events[-1].trigger == "high_pairwise_divergence"
        assert engine.events[-1].divergence == round(measured, 3)