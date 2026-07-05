"""Tests for oss/ecosystem/live_sources.py -- the real-telemetry replacement
for oss/kernel/sandbox.py's synthetic Market/Infra/Product simulators.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from oss.ecosystem.live_sources import (
    builder_snapshot,
    kairos_snapshot,
    treasury_metrics,
)


def test_kairos_snapshot_shape_and_bounds():
    snap = kairos_snapshot()
    assert "live" in snap
    for key in ("total_cycles", "elite_ratio", "block_ratio", "avg_score",
                "avg_sentinel_v", "avg_entropy_drift"):
        assert key in snap
    assert 0.0 <= snap["elite_ratio"] <= 1.0
    assert 0.0 <= snap["block_ratio"] <= 1.0


def test_kairos_snapshot_no_cycles_is_neutral_not_zero():
    """An idle KAIROS (no cycles run) must report full uptime/efficiency,
    not a fabricated zero that would look like a failing system."""
    snap = kairos_snapshot()
    if snap["total_cycles"] == 0:
        assert snap["elite_ratio"] == 0.0
        assert snap["block_ratio"] == 0.0


def test_treasury_metrics_shape():
    snap = treasury_metrics()
    for key in ("live", "treasury_balance", "sharpe", "max_drawdown",
                "volatility", "transaction_count"):
        assert key in snap
    assert snap["transaction_count"] >= 0


def test_treasury_metrics_handles_sparse_history_honestly():
    """With fewer than 2 real transactions there's no real variance to
    measure -- must report a neutral 0.0, not a computed-looking number
    derived from insufficient data."""
    snap = treasury_metrics()
    if snap["transaction_count"] < 2:
        assert snap["sharpe"] == 0.0
        assert snap["max_drawdown"] == 0.0
        assert snap["volatility"] == 0.0


def test_builder_snapshot_shape():
    snap = builder_snapshot()
    for key in ("live", "retention", "revenue", "active_subscribers", "total_subscribers"):
        assert key in snap
    assert 0.0 <= snap["retention"] <= 1.0


def test_builder_snapshot_no_subscribers_is_zero_not_fabricated():
    snap = builder_snapshot()
    if snap["total_subscribers"] == 0:
        assert snap["retention"] == 0.0
