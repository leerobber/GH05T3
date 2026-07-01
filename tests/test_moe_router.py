"""Tests for MOERouter — intent-based dispatch to expert agents."""
import os
import sys
import pytest

SOVEREIGN_PATH = os.environ.get("SOVEREIGN_CORE_PATH", "")
if SOVEREIGN_PATH and SOVEREIGN_PATH not in sys.path:
    sys.path.insert(0, SOVEREIGN_PATH)

pytest.importorskip("src.kernel.runtime", reason="sovereign-core not on SOVEREIGN_CORE_PATH")

from src.semantics.semantic_word import SemanticWord, IntentType, WordType, ChannelType
from backend.core.moe_router import MOERouter


@pytest.fixture()
def router():
    r = MOERouter()
    r.load_experts()
    return r


def test_load_experts_registers_all(router):
    assert router._registry.has("planner")
    assert router._registry.has("critic")
    assert router._registry.has("builder")
    assert router._registry.has("biz")
    assert router._registry.has("infra")


def test_route_plan_intent(router):
    word = SemanticWord.make(intent=IntentType.PLAN).encode()
    out = router.route(word)
    assert len(out) >= 1


def test_route_critique_intent(router):
    word = SemanticWord.make(intent=IntentType.CRITIQUE).encode()
    out = router.route(word)
    assert len(out) >= 1


def test_route_reflect_intent(router):
    word = SemanticWord.make(intent=IntentType.REFLECT).encode()
    out = router.route(word)
    assert len(out) >= 1


def test_route_emit_intent(router):
    word = SemanticWord.make(intent=IntentType.EMIT).encode()
    out = router.route(word)
    assert len(out) >= 1


def test_route_summarize_intent(router):
    word = SemanticWord.make(intent=IntentType.SUMMARIZE).encode()
    out = router.route(word)
    assert len(out) >= 1


def test_route_query_intent(router):
    word = SemanticWord.make(intent=IntentType.QUERY).encode()
    out = router.route(word)
    assert len(out) >= 1


def test_route_returns_semantic_words(router):
    word = SemanticWord.make(intent=IntentType.PLAN).encode()
    out = router.route(word)
    for w in out:
        sw = SemanticWord.decode(w)
        assert sw.type == int(WordType.RESULT)


def test_route_unknown_intent_falls_back_to_planner(router):
    word = SemanticWord.make(intent=IntentType.NONE).encode()
    out = router.route(word)
    assert len(out) >= 1


def test_router_not_loaded_raises():
    r = MOERouter()
    word = SemanticWord.make(intent=IntentType.PLAN).encode()
    with pytest.raises(RuntimeError, match="not loaded"):
        r.route(word)


def test_status_after_routing(router):
    word = SemanticWord.make(intent=IntentType.PLAN).encode()
    router.route(word)
    s = router.status()
    assert s["agents"] >= 5
