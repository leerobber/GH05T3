"""OSS Environment Layer runtime tests."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
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


def test_story_editor_start_includes_greeting():
    runtime = EnvironmentRuntime()
    session = runtime.start_session(domain="story_editor", metadata={"project": "pilot"})
    snap = runtime.snapshot(session.session_id)

    assert snap["domain"] == "story_editor"
    assert snap["state"]["metadata"]["project"] == "pilot"
    assert "form is the story" in snap["state"]["greeting"].lower()
    assert snap["state"]["story_editor_stage"] == 0
    assert snap["state"]["step"] == 0


@pytest.mark.anyio
async def test_story_editor_step_advances_intake():
    runtime = EnvironmentRuntime()
    session = runtime.start_session(domain="story_editor")
    await runtime.step(
        session.session_id,
        action={"message": "Half-hour comedy pilot, blank page, only a logline."},
    )
    snap = runtime.snapshot(session.session_id)

    assert snap["state"]["step"] == 1
    assert snap["state"]["story_editor_stage"] == 1
    assert snap["state"]["story"]["form_and_stage"] == (
        "Half-hour comedy pilot, blank page, only a logline."
    )
    assert "one sentence" in snap["state"]["last_reply"].lower()


def test_story_editor_api_start_step_and_snapshot():
    app = FastAPI()
    app.include_router(oss_router, prefix="/oss")
    client = TestClient(app)

    start_resp = client.post(
        "/oss/world/session",
        json={"domain": "story_editor", "metadata": {"writer": "test"}},
    )
    assert start_resp.status_code == 200
    start_body = start_resp.json()
    session_id = start_body["session_id"]
    assert start_body["domain"] == "story_editor"
    assert "greeting" in start_body["state"]

    snapshot_resp = client.get(f"/oss/world/session/{session_id}")
    assert snapshot_resp.status_code == 200
    assert snapshot_resp.json()["session_id"] == session_id

    step_resp = client.post(
        f"/oss/world/session/{session_id}/step",
        json={"action": {"message": "Literary novel, 10k words drafted."}},
    )
    assert step_resp.status_code == 200
    step_body = step_resp.json()
    assert step_body["state"]["step"] == 1
    assert step_body["state"]["story"]["form_and_stage"] == "Literary novel, 10k words drafted."

    missing_resp = client.get("/oss/world/session/not-a-real-id")
    assert missing_resp.status_code == 404