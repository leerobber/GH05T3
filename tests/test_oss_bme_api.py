"""BME OSS API contracts."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from oss.api.router import router as oss_router
from oss.pact.provider_states import router as pact_router


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(oss_router, prefix="/oss")
    return TestClient(app)


def test_bme_status_contract():
    client = _client()
    r = client.get("/oss/bme/status")
    assert r.status_code == 200
    body = r.json()
    assert "active_slots" in body
    assert "universe_distribution" in body
    assert "role_counts" in body
    assert "trait_summary" in body
    assert "reward_summary" in body


def test_bme_cycle_contract():
    client = _client()
    r = client.post(
        "/oss/bme/cycle",
        json={
            "cycles": 1,
            "target_universe": 4,
            "allow_migration": False,
            "allow_promotion": True,
            "allow_breakthrough": True,
            "push_sovereign_core": False,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["cycle_completed"] is True
    assert body["ran"] == 1
    assert body["target_universe"] == 4
    assert "universe_distribution" in body
    assert "role_counts" in body


def test_bme_flagship_profiles():
    client = _client()
    r = client.get("/oss/bme/flagships")
    assert r.status_code == 200
    body = r.json()
    assert "profiles" in body
    assert "DataMycologist" in body["profiles"]

    detail = client.get("/oss/bme/flagships/DataMycologist")
    assert detail.status_code == 200
    detail_body = detail.json()
    assert detail_body["found"] is True
    assert detail_body["preferred_universe"] == 4


def test_provider_states_endpoint():
    app = FastAPI()
    app.include_router(pact_router)
    client = TestClient(app)

    r = client.post("/_pact/provider_states", json={"state": "MVS is ready"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["state"] == "MVS is ready"
