"""
OSS Contract / Integration Smoke Tests

These act as consumer-driven contract tests for the public /oss surface.

They assert stable response shapes that gateway consumers and SovereignCore
bridges can rely on. Use matchers (loose equality where possible) to avoid
brittle contracts.

Run in CI as:
  python -m pytest tests/test_oss_contract.py -q -m "not live"

They are intentionally lightweight (no full live inference required).
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Mount the real OSS router exactly as the gateway does
from oss.api.router import router as oss_router


@pytest.fixture(scope="module")
def oss_client():
    app = FastAPI()
    app.include_router(oss_router, prefix="/oss")
    return TestClient(app)


def test_health_contract(oss_client):
    """Minimal contract: /health must be stable for health checks / can-i-deploy."""
    r = oss_client.get("/oss/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["layer"] == "oss"
    assert "version" in body


def test_mvs_status_contract(oss_client):
    """Consumer (gateway + Sovereign) expects at least these keys from MVS bridge."""
    r = oss_client.get("/oss/mvs/status")
    assert r.status_code == 200
    body = r.json()
    # Core contract fields (loose — use .get for optionals)
    assert "available" in body
    if body.get("available"):
        assert "genomes" in body
        assert "loop_state" in body
        loop = body["loop_state"]
        assert "species" in loop or "aggregate" in body.get("loop_state", {})


def test_mvs_cycle_contract(oss_client):
    """POST /oss/mvs/cycle must accept the documented payload and return run results."""
    payload = {"cycles": 2, "dry_run": True}
    r = oss_client.post("/oss/mvs/cycle", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert "ran" in body
    assert body["ran"] == 2
    assert "dry_run" in body and body["dry_run"] is True
    assert "results" in body
    assert isinstance(body["results"], list)


def test_omni_route_contract(oss_client):
    """ /oss/omni/route is the richer MoE exposure. Must not 500 and return route info."""
    r = oss_client.post("/oss/omni/route", json={"prompt": "Test MoE routing for contract."})
    assert r.status_code == 200
    body = r.json()
    # At least one of these must be present in successful or degraded response
    assert any(k in body for k in ("adapter_bucket", "route", "error"))


def test_registry_status_contract(oss_client):
    """Registry status is used by consumers for genome linkage checks."""
    r = oss_client.get("/oss/registry/status")
    assert r.status_code == 200
    body = r.json()
    # We treat personas as canonical now
    assert "genome_count" in body or "source" in body


def test_economy_unified_contract(oss_client):
    """Economy unified view for SovereignCore bridge consumers."""
    r = oss_client.get("/oss/economy/unified")
    assert r.status_code == 200
    body = r.json()
    assert "currency" in body
    assert "local_online" in body
    assert "sovereign_core_online" in body
