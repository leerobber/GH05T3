"""
WSL integration tests — verify that WSL-hosted GH05T3 services are reachable
from Windows and respond correctly.

These tests are skipped automatically unless WSL_SERVICES_UP=1 is set.
To run:
    $env:WSL_SERVICES_UP = "1"
    pytest tests/test_wsl_integration.py -v

Start WSL services first:
    wsl bash /mnt/c/Users/leer4/GH05T3/scripts/wsl_start.sh
"""
from __future__ import annotations

import os
import time

import pytest
import requests

# WSL services bind 0.0.0.0 inside WSL, so from Windows they're on localhost
_BACKEND_URL = os.environ.get("WSL_BACKEND_URL", "http://localhost:8001")
_GATEWAY_URL = os.environ.get("WSL_GATEWAY_URL", "http://localhost:8002")
_TIMEOUT     = 5


pytestmark = pytest.mark.wsl  # entire module skips when WSL_SERVICES_UP not set


# ── Health checks ─────────────────────────────────────────────────────────────

def test_wsl_backend_health():
    """Backend API on :8001 returns 200 OK."""
    r = requests.get(f"{_BACKEND_URL}/health", timeout=_TIMEOUT)
    assert r.status_code == 200, f"backend /health returned {r.status_code}"


def test_wsl_gateway_health():
    """Gateway on :8002 returns 200 OK."""
    r = requests.get(f"{_GATEWAY_URL}/health", timeout=_TIMEOUT)
    assert r.status_code == 200, f"gateway /health returned {r.status_code}"


def test_wsl_gateway_agents_endpoint():
    """Gateway /agents endpoint returns a list."""
    r = requests.get(f"{_GATEWAY_URL}/agents", timeout=_TIMEOUT)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, (list, dict)), f"unexpected /agents response: {data!r}"


def test_wsl_backend_swarm_status():
    """Backend /swarm/status returns swarm stats (may be empty on fresh start)."""
    r = requests.get(f"{_BACKEND_URL}/swarm/status", timeout=_TIMEOUT)
    assert r.status_code in (200, 404), (
        f"/swarm/status returned unexpected {r.status_code}"
    )


def test_wsl_ollama_reachable_via_gateway():
    """Gateway can reach Ollama (Windows host) — no 503 on /models."""
    r = requests.get(f"{_GATEWAY_URL}/models", timeout=_TIMEOUT)
    # 200 = Ollama up, 503 = Ollama down but gateway itself is alive
    assert r.status_code in (200, 503), (
        f"/models returned unexpected {r.status_code}"
    )
    if r.status_code == 503:
        pytest.xfail("Ollama not running on Windows host — start Ollama and retry")


def test_wsl_round_trip_latency():
    """Windows→WSL gateway round-trip is under 500ms."""
    start = time.perf_counter()
    r = requests.get(f"{_GATEWAY_URL}/health", timeout=_TIMEOUT)
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert r.status_code == 200
    assert elapsed_ms < 500, (
        f"WSL round-trip too slow: {elapsed_ms:.0f}ms (expected <500ms)"
    )
