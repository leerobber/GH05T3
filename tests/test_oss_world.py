"""OSS Environment Layer runtime tests."""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from oss.api.router import router as oss_router
from oss.world.runtime import EnvironmentRuntime, list_domains


def test_list_domains_returns_phase2_domains():
    domains = list_domains()
    assert domains == ["story_editor", "training", "frontier"]


def test_runtime_start_session_and_snapshot():
    runtime = EnvironmentRuntime()
    session = runtime.start_session(
        domain="training",
        metadata={"scenario": "gateway_latency"},
    )
    snap = runtime.snapshot(session.session_id)

    assert snap["session_id"] == session.session_id
    assert snap["domain"] == "training"
    assert snap["state"]["metadata"]["scenario"] == "gateway_latency"
    assert snap["state"]["step"] == 0


def test_world_session_api_route():
    app = FastAPI()
    app.include_router(oss_router, prefix="/oss")
    client = TestClient(app)

    domains_resp = client.get("/oss/world/domains")
    assert domains_resp.status_code == 200
    assert "story_editor" in domains_resp.json()["domains"]

    session_resp = client.post(
        "/oss/world/session",
        json={"domain": "frontier", "metadata": {"node": "ghostdeck"}},
    )
    assert session_resp.status_code == 200
    body = session_resp.json()
    assert body["domain"] == "frontier"
    assert body["state"]["metadata"]["node"] == "ghostdeck"