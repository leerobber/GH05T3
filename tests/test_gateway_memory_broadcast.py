"""Gateway POST /memory/store and POST /swarm/broadcast contract tests."""
from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("AETHYRO_SKIP_LICENSE", "1")

_ROOT = Path(__file__).resolve().parents[1]
_BACKEND = str(_ROOT / "backend")


def _ensure_backend_imports() -> None:
    """Gateway must load backend/swarm, not the repo-root swarm shim."""
    os.chdir(_BACKEND)
    root_str = str(_ROOT)
    for entry in list(sys.path):
        if entry in (root_str, ""):
            sys.path.remove(entry)
    if _BACKEND in sys.path:
        sys.path.remove(_BACKEND)
    sys.path.insert(0, _BACKEND)

    for name in list(sys.modules):
        if name == "gateway_v3" or name == "swarm" or name.startswith("swarm."):
            mod_file = getattr(sys.modules[name], "__file__", "") or ""
            normalized = mod_file.replace("\\", "/")
            if not mod_file or _BACKEND.replace("\\", "/") not in normalized:
                del sys.modules[name]


_ensure_backend_imports()


@pytest.fixture
def gateway_client(monkeypatch):
    _ensure_backend_imports()

    @asynccontextmanager
    async def _noop_lifespan(app):
        yield

    import gateway_v3

    monkeypatch.setattr(gateway_v3.app.router, "lifespan_context", _noop_lifespan)
    monkeypatch.delenv("GH05T3_API_TOKEN", raising=False)

    stored: list[dict] = []

    def fake_store(content, room="general", tags=None):
        shard = {
            "id": 42,
            "room": room,
            "content": content,
            "timestamp": 1.0,
            "tags": tags or [],
        }
        stored.append(shard)
        return shard

    emitted: list[dict] = []

    async def fake_emit(**kwargs):
        emitted.append(kwargs)

    monkeypatch.setattr(gateway_v3.memory, "store", fake_store)
    monkeypatch.setattr(gateway_v3.bus, "emit", fake_emit)

    client = TestClient(gateway_v3.app)
    client._stored = stored
    client._emitted = emitted
    return client


def test_memory_store_request_model_defaults():
    _ensure_backend_imports()
    from gateway_v3 import MemoryStoreRequest

    req = MemoryStoreRequest(content="hello")
    assert req.type is None
    assert req.domain is None
    assert req.tags == []


def test_broadcast_request_model_defaults():
    _ensure_backend_imports()
    from gateway_v3 import BroadcastRequest

    req = BroadcastRequest(content="ping")
    assert req.src == "API"
    assert req.channel == "#broadcast"
    assert req.msg_type == "chat"


def test_parse_msg_type_maps_thought_and_unknown():
    _ensure_backend_imports()
    from gateway_v3 import MsgType, _parse_msg_type

    assert _parse_msg_type("thought") == MsgType.THOUGHT
    assert _parse_msg_type("THOUGHT") == MsgType.THOUGHT
    assert _parse_msg_type("nope") == MsgType.CHAT


def test_memory_store_maps_type_to_room(gateway_client):
    payload = {
        "content": "captured thought",
        "type": "recall",
        "source": "sovereign_recall/github",
        "domain": "agent_systems",
        "confidence": 0.85,
        "tags": ["recall", "github", "agent_systems"],
    }
    resp = gateway_client.post("/memory/store", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["room"] == "recall"
    assert body["content"] == payload["content"]
    assert body["tags"] == payload["tags"]
    assert gateway_client._stored[0]["room"] == "recall"


def test_memory_store_falls_back_to_domain_then_general(gateway_client):
    r1 = gateway_client.post(
        "/memory/store",
        json={"content": "a", "domain": "training", "tags": []},
    )
    assert r1.status_code == 200
    assert r1.json()["room"] == "training"

    r2 = gateway_client.post("/memory/store", json={"content": "b", "tags": []})
    assert r2.status_code == 200
    assert r2.json()["room"] == "general"


def test_swarm_broadcast_accepts_json_body(gateway_client):
    payload = {
        "content": "CHRONICLE found 3 examples",
        "src": "CHRONICLE",
        "channel": "#broadcast",
        "msg_type": "thought",
    }
    resp = gateway_client.post("/swarm/broadcast", json=payload)
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}

    emit = gateway_client._emitted[0]
    assert emit["src"] == "CHRONICLE"
    assert emit["content"] == payload["content"]
    assert emit["channel"] == "#broadcast"
    assert emit["msg_type"].value == "thought"


def test_swarm_broadcast_defaults_and_unknown_msg_type(gateway_client):
    resp = gateway_client.post("/swarm/broadcast", json={"content": "hello"})
    assert resp.status_code == 200

    emit = gateway_client._emitted[0]
    assert emit["src"] == "API"
    assert emit["channel"] == "#broadcast"
    assert emit["msg_type"].value == "chat"

    gateway_client.post(
        "/swarm/broadcast",
        json={"content": "x", "msg_type": "not_a_real_type"},
    )
    assert gateway_client._emitted[1]["msg_type"].value == "chat"