"""Sovereign economy bridge tests."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from oss.adapters.sovereign import unified_economy_snapshot


def test_unified_economy_snapshot_local_fields():
    with patch("oss.adapters.sovereign.external_economy_available", return_value=False), \
         patch("oss.adapters.sovereign.sovereign_core_available", return_value=False), \
         patch("oss.adapters.sovereign.fetch_external_economy_stats", return_value={}), \
         patch("oss.adapters.sovereign.fetch_sovereign_health", return_value={"status": "unreachable"}), \
         patch("oss.adapters.marketplace.list_jobs", return_value=[]):
        snap = unified_economy_snapshot()
        data = snap.to_dict()
        assert data["currency"] == "NC"
        assert data["local_online"] is True
        assert data["external_economy_online"] is False
        assert "local_balances" in data


def test_unified_economy_snapshot_external_online():
    with patch("oss.adapters.sovereign.external_economy_available", return_value=True), \
         patch("oss.adapters.sovereign.sovereign_core_available", return_value=True), \
         patch("oss.adapters.sovereign.fetch_external_economy_stats", return_value={
             "tick": 42, "agents": {"total": 12}, "economy_health": {"score": 0.9},
         }), \
         patch("oss.adapters.sovereign.fetch_sovereign_health", return_value={"status": "ok"}), \
         patch("oss.adapters.marketplace.list_jobs", return_value=[{"id": "j1"}]):
        snap = unified_economy_snapshot()
        data = snap.to_dict()
        assert data["external_economy_online"] is True
        assert data["sovereign_core_online"] is True
        assert data["pending_jobs"] == 1
        assert data["external_stats"]["tick"] == 42