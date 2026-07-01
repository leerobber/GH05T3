"""VolatilityWorld v1 tests — Phase 2 Week 3 gate."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from backend.oss.world.volatility_world import (
    VolatilityModel,
    VolatilityWorld,
)


def test_generate_series_has_regimes_and_id():
    world = VolatilityWorld(length=200, seed=42)
    data = world.generate_series()
    assert "series_id" in data
    assert len(data["series"]) == 200
    assert data["regimes"] == [0.1, 0.3, 0.6]


def test_generate_challenge_attaches_preview():
    world = VolatilityWorld(length=100, seed=7)
    raw = world.generate_series()
    ch = world.generate_challenge(raw["series_id"])
    assert ch.series_id == raw["series_id"]
    assert len(ch.series_preview) <= 32
    assert 0.0 <= ch.difficulty <= 1.0


def test_submit_and_evaluate_model_by_id():
    world = VolatilityWorld(length=300, seed=99)
    raw = world.generate_series()
    model = VolatilityModel(
        agent_id="theorist_01",
        description="Regime-switching volatility with stochastic transitions",
        code="def predict(series): return regime_aware_volatility(series)",
        parameters={"regimes": 3, "switch_prob": 0.05},
    )
    mid = world.submit_model(model)
    result = world._evaluate_by_ids(mid, raw["series_id"])
    assert result["weighted_score"] > 0.4
    assert "feedback" in result
    assert world.get_evaluation(mid, raw["series_id"]) is not None


def test_legacy_evaluate_model_text_path():
    world = VolatilityWorld(seed=1)
    data = world.generate_series(length=50)
    score = world.evaluate_model(
        "Regime-switching stochastic volatility process with transition dynamics",
        data,
    )
    assert 0.0 <= score <= 1.0
    assert score >= 0.5


def test_evaluate_missing_model_raises():
    world = VolatilityWorld(seed=2)
    raw = world.generate_series()
    with pytest.raises(KeyError, match="model"):
        world._evaluate_by_ids("missing", raw["series_id"])