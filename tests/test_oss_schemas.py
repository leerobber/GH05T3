"""OSS schema contract tests."""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from oss.schemas.message import BusMessage, MessageType
from oss.schemas.economy import CreditEvent, CreditSource, EconomySnapshot
from oss.schemas.mesh import MeshSnapshot, PeerRecord, PeerStatus


def test_bus_message_roundtrip():
    msg = BusMessage(
        channel="#oss/tasks",
        msg_type=MessageType.TASK,
        src="OrchestrationLayer",
        dst="ORACLE",
        content="audit webhook handler",
        message_id="abc123",
        timestamp=1700000000.0,
    )
    restored = BusMessage.from_dict(msg.to_dict())
    assert restored.channel == "#oss/tasks"
    assert restored.msg_type == MessageType.TASK
    assert restored.dst == "ORACLE"


def test_credit_event_from_ledger_row():
    ev = CreditEvent.from_ledger_row({
        "id": 1,
        "ts": 1700000000.0,
        "agent_id": "ORACLE",
        "delta": 25.0,
        "balance": 125.0,
        "reason": "job complete",
        "source": "neuro_coin",
    })
    assert ev.agent_id == "ORACLE"
    assert ev.source == CreditSource.NEURO_COIN
    assert ev.balance == 125.0


def test_mesh_snapshot_from_gateway_contract():
    raw = {
        "self": {"label": "TatorTot", "url": "http://100.94.227.81:8002"},
        "peers": [
            {"label": "node-b", "ip": "100.1.2.3", "url": "http://100.1.2.3:8002",
             "status": "ok", "agents": 5, "version": "3.0.0"},
        ],
        "mesh": {
            "discovery": {"refresh": "/peers/refresh", "ping": "/peers/ping"},
            "github_relay": {"sync": "/github/mesh/sync"},
        },
        "tailscale_configured": True,
    }
    snap = MeshSnapshot.from_gateway_contract(raw)
    assert snap.tailscale_configured is True
    assert len(snap.peers) == 1
    assert snap.peers[0].status == PeerStatus.ONLINE
    assert snap.routes["refresh"] == "/peers/refresh"


def test_peer_record_from_gateway_peer():
    peer = PeerRecord.from_gateway_peer({"label": "edge", "status": "degraded", "agents": 2})
    assert peer.status == PeerStatus.DEGRADED
    assert peer.agents == 2


def test_economy_snapshot_serializes():
    snap = EconomySnapshot(currency="NC", total_agents=3, pending_jobs=1)
    data = snap.to_dict()
    assert data["currency"] == "NC"
    assert data["pending_jobs"] == 1