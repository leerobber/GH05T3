"""Tests for the five GH05T3 expert agent classes."""
import os
import sys
import pytest

SOVEREIGN_PATH = os.environ.get("SOVEREIGN_CORE_PATH", "")
if SOVEREIGN_PATH and SOVEREIGN_PATH not in sys.path:
    sys.path.insert(0, SOVEREIGN_PATH)

pytest.importorskip("src.agents.base_agent", reason="sovereign-core not on SOVEREIGN_CORE_PATH")

from src.isa.instruction import Instruction
from src.isa.opcodes import Opcode
from src.semantics.semantic_word import SemanticWord, WordType, IntentType
from src.agents.agent_state import AgentState

from backend.experts.planner_agent import PlannerAgent
from backend.experts.critic_agent import CriticAgent
from backend.experts.builder_agent import BuilderAgent
from backend.experts.biz_agent import BizAgent
from backend.experts.infra_agent import InfraAgent


# ── PlannerAgent ─────────────────────────────────────────────────────────────

def test_planner_plan_emits_one_word():
    agent = PlannerAgent(id=1)
    task = SemanticWord.make(intent=IntentType.PLAN).encode()
    agent.receive(task)
    out = agent.step(Instruction(opcode=Opcode.PLAN))
    assert len(out) == 1


def test_planner_result_intent_is_plan():
    agent = PlannerAgent(id=1)
    agent.receive(SemanticWord.make(intent=IntentType.PLAN).encode())
    out = agent.step(Instruction(opcode=Opcode.PLAN))
    sw = SemanticWord.decode(out[0])
    assert sw.intent == int(IntentType.PLAN)
    assert sw.type == int(WordType.RESULT)


def test_planner_clears_inbox():
    agent = PlannerAgent(id=1)
    agent.receive(SemanticWord.make().encode())
    agent.step(Instruction(opcode=Opcode.PLAN))
    assert len(agent.inbox) == 0


def test_planner_logs_step():
    agent = PlannerAgent(id=1)
    agent.receive(SemanticWord.make().encode())
    agent.step(Instruction(opcode=Opcode.PLAN))
    assert any(entry[0] == "PLAN" for entry in agent.log)


# ── CriticAgent ──────────────────────────────────────────────────────────────

def test_critic_critique_emits_score():
    agent = CriticAgent(id=2)
    plan = SemanticWord.make(intent=IntentType.PLAN, confidence=0.9).encode()
    agent.receive(plan)
    out = agent.step(Instruction(opcode=Opcode.CRITIQUE))
    assert len(out) >= 1


def test_critic_lowers_confidence():
    agent = CriticAgent(id=2)
    plan = SemanticWord.make(intent=IntentType.PLAN, confidence=0.9).encode()
    agent.receive(plan)
    out = agent.step(Instruction(opcode=Opcode.CRITIQUE))
    sw = SemanticWord.decode(out[0])
    assert sw.confidence_f <= 0.9


def test_critic_reflect_emits_result():
    agent = CriticAgent(id=2)
    agent.receive(SemanticWord.make().encode())
    out = agent.step(Instruction(opcode=Opcode.REFLECT))
    assert len(out) == 1
    sw = SemanticWord.decode(out[0])
    assert sw.intent == int(IntentType.REFLECT)


def test_critic_empty_inbox_still_emits():
    agent = CriticAgent(id=2)
    out = agent.step(Instruction(opcode=Opcode.CRITIQUE))
    assert len(out) == 1


# ── BuilderAgent ─────────────────────────────────────────────────────────────

def test_builder_emit_returns_inbox():
    agent = BuilderAgent(id=3)
    word = SemanticWord.make(intent=IntentType.EMIT).encode()
    agent.receive(word)
    out = agent.step(Instruction(opcode=Opcode.EMIT_RESULT))
    assert word in out


def test_builder_empty_inbox_emits_default():
    agent = BuilderAgent(id=3)
    out = agent.step(Instruction(opcode=Opcode.EMIT_RESULT))
    assert len(out) == 1


# ── BizAgent ─────────────────────────────────────────────────────────────────

def test_biz_summarize_emits_memory_word():
    agent = BizAgent(id=4)
    agent.receive(SemanticWord.make().encode())
    out = agent.step(Instruction(opcode=Opcode.SUMMARIZE_MEMORY))
    assert len(out) == 1
    sw = SemanticWord.decode(out[0])
    assert sw.intent == int(IntentType.SUMMARIZE)


# ── InfraAgent ───────────────────────────────────────────────────────────────

def test_infra_run_workflow_emits_tool_word():
    agent = InfraAgent(id=5)
    out = agent.step(Instruction(opcode=Opcode.RUN_WORKFLOW, args=[42]))
    assert len(out) == 1
    sw = SemanticWord.decode(out[0])
    assert sw.type == int(WordType.TOOL)


def test_infra_workflow_payload_ref():
    agent = InfraAgent(id=5)
    out = agent.step(Instruction(opcode=Opcode.RUN_WORKFLOW, args=[7]))
    sw = SemanticWord.decode(out[0])
    assert sw.payload_ref == 7


# ── IDLE state after each step ───────────────────────────────────────────────

@pytest.mark.parametrize("agent_cls,opcode", [
    (PlannerAgent, Opcode.PLAN),
    (CriticAgent,  Opcode.CRITIQUE),
    (BuilderAgent, Opcode.EMIT_RESULT),
    (BizAgent,     Opcode.SUMMARIZE_MEMORY),
    (InfraAgent,   Opcode.RUN_WORKFLOW),
])
def test_agent_returns_to_idle(agent_cls, opcode):
    agent = agent_cls(id=99)
    agent.step(Instruction(opcode=opcode))
    assert agent.state == AgentState.IDLE
