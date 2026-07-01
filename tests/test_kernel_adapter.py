"""Tests for KernelAdapter — glue between GH05T3 and sovereign-core Runtime."""
import os
import sys
import pytest

SOVEREIGN_PATH = os.environ.get("SOVEREIGN_CORE_PATH", "")
if SOVEREIGN_PATH and SOVEREIGN_PATH not in sys.path:
    sys.path.insert(0, SOVEREIGN_PATH)

sovereign = pytest.importorskip("src.kernel.runtime", reason="sovereign-core not on SOVEREIGN_CORE_PATH")

from backend.integration.kernel_adapter import KernelAdapter
from src.isa.opcodes import Opcode
from src.semantics.semantic_word import SemanticWord, IntentType, WordType


def test_spawn_returns_int():
    ka = KernelAdapter()
    aid = ka.spawn("planner")
    assert isinstance(aid, int)
    assert ka.role_of(aid) == "planner"


def test_spawn_multiple():
    ka = KernelAdapter()
    a1 = ka.spawn("planner")
    a2 = ka.spawn("critic")
    assert a1 != a2
    assert ka.role_of(a2) == "critic"


def test_kill_removes_agent():
    ka = KernelAdapter()
    aid = ka.spawn("builder")
    ka.kill(aid)
    assert ka.role_of(aid) == "unknown"
    assert aid not in ka.runtime.agents


def test_encode_decode_roundtrip():
    ka = KernelAdapter()
    word_int = ka.encode(intent=IntentType.PLAN, priority=200, confidence=0.9)
    sw = ka.decode(word_int)
    assert sw.intent == int(IntentType.PLAN)
    assert sw.priority == 200
    assert abs(sw.confidence_f - 0.9) < 0.001


def test_send_delivers_to_inbox():
    ka = KernelAdapter()
    sender = ka.spawn("planner")
    receiver = ka.spawn("critic")
    word = ka.encode(intent=IntentType.PLAN)
    ka.send(sender, receiver, word)
    assert word in ka.runtime.agents[receiver].inbox


def test_broadcast_skips_sender():
    ka = KernelAdapter()
    ids = [ka.spawn("planner") for _ in range(3)]
    word = ka.encode()
    ka.broadcast(ids[0], word)
    assert word not in ka.runtime.agents[ids[0]].inbox
    assert word in ka.runtime.agents[ids[1]].inbox
    assert word in ka.runtime.agents[ids[2]].inbox


def test_payload_store_and_load():
    ka = KernelAdapter()
    ref = ka.store({"result": "ok"})
    assert ka.load(ref) == {"result": "ok"}
    assert ka.load(9999) is None


def test_hook_fires_on_spawn():
    ka = KernelAdapter()
    events = []
    ka.add_hook(lambda ev, **kw: events.append(ev))
    ka.spawn("infra")
    assert "spawn" in events


def test_dispatch_plan():
    ka = KernelAdapter()
    aid = ka.spawn("planner")
    word = ka.encode(intent=IntentType.PLAN)
    ka.send(0, aid, word)
    emitted = ka.dispatch(aid, Opcode.PLAN)
    assert len(emitted) >= 1


def test_status_includes_roles():
    ka = KernelAdapter()
    ka.spawn("planner")
    s = ka.status()
    assert "agents" in s
    assert "roles" in s
    assert "planner" in s["roles"].values()
