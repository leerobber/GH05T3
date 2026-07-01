"""
Unified pytest configuration for the GH05T3 / Aethyro test suite.

Covers all tests under tests/ (previously split across tests/ and backend/tests/).
WSL integration tests skip automatically when WSL services aren't reachable.
Live-server tests skip automatically when REACT_APP_BACKEND_URL is not set.
"""
import os
import sys
from pathlib import Path

# ── sys.path: ensure backend/ is importable for tests that use bare imports ──
_REPO_ROOT = Path(__file__).resolve().parents[1]
_BACKEND   = _REPO_ROOT / "backend"
for _p in (str(_REPO_ROOT), str(_BACKEND)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ── License gate bypass for all tests ────────────────────────────────────────
os.environ.setdefault("AETHYRO_SKIP_LICENSE", "1")
os.environ.setdefault("GH05T3_TEST_MODE", "1")

import pytest


# ── Markers ───────────────────────────────────────────────────────────────────

def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "live: requires a running backend server (skipped when "
        "REACT_APP_BACKEND_URL is not set)",
    )
    config.addinivalue_line(
        "markers",
        "wsl: requires reachable WSL services on localhost:8001/8002 "
        "(skipped when WSL_SERVICES_UP env var is not set)",
    )
    config.addinivalue_line(
        "markers",
        "integration: heavy integration test — opt-in only",
    )


# ── Auto-skip: live server tests ──────────────────────────────────────────────

_LIVE_MODULES = {
    "test_gh05t3",
    "test_gh05t3_phase2",
    "test_gh05t3_phase3",
    "test_gh05t3_phase4",
    "test_swarm",
}

# ── Auto-skip: WSL integration tests ─────────────────────────────────────────

_WSL_MODULES = {"test_wsl_integration"}


def pytest_collection_modifyitems(config, items):
    skip_live = pytest.mark.skip(
        reason="live server not available (set REACT_APP_BACKEND_URL to enable)"
    )
    skip_wsl = pytest.mark.skip(
        reason="WSL services not running (set WSL_SERVICES_UP=1 and start "
               "wsl_start.sh to enable)"
    )

    has_backend_url  = bool(os.environ.get("REACT_APP_BACKEND_URL"))
    has_wsl_services = bool(os.environ.get("WSL_SERVICES_UP"))

    for item in items:
        module = getattr(item, "module", None)
        if module is None:
            continue
        name = getattr(module, "__name__", "").split(".")[-1]

        if not has_backend_url and name in _LIVE_MODULES:
            item.add_marker(skip_live)
        if not has_wsl_services and name in _WSL_MODULES:
            item.add_marker(skip_wsl)
