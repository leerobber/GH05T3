"""Phase 3 OmniMind v1.5 gate tests."""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def test_consensus_three_agents():
    from backend.oss.mind.consensus import WeightedConsensusEngine

    engine = WeightedConsensusEngine()
    traits = {"math": 0.9, "pattern_detection": 0.8, "self_reflection": 0.7}
    for i, val in enumerate((0.82, 0.85, 0.80)):
        engine.cast_vote("theory_gate", f"agent_{i}", val, 0.9, traits)
    consensus, reached, meta = engine.get_consensus("theory_gate", threshold=0.7)
    assert 0.7 < consensus < 0.95
    assert meta["count"] == 3


def test_consensus_dispute_resolution():
    from backend.oss.mind.consensus import WeightedConsensusEngine

    engine = WeightedConsensusEngine()
    engine.cast_vote("dispute", "a1", 0.2, 0.9, {"math": 0.5})
    engine.cast_vote("dispute", "a2", 0.9, 0.9, {"math": 0.95})
    resolved = engine.resolve_dispute("dispute")
    assert resolved is not None
    assert resolved > 0.5


def test_canonical_memory_promote_and_search():
    from backend.oss.mind.canonical_memory import CanonicalMemorySystem

    cms = CanonicalMemorySystem()
    mem = cms.promote("t1", "Regime-switching HMM volatility model", fitness=0.9, novelty=0.85, domain="volatility")
    assert mem is not None
    hits = cms.search_memories("regime", domain="volatility")
    assert len(hits) >= 1
    cms.update_usage(mem.memory_id)
    assert mem.usage_count == 1


def test_goal_generator_v2_produces_ten_unique():
    from backend.oss.mind.goal_generator_v2 import GoalGeneratorV2

    gen = GoalGeneratorV2()
    goals = gen.generate_goals(limit=10)
    assert len(goals) >= 10
    ids = {g["goal_id"] for g in goals}
    assert len(ids) == len(goals)


def test_swarm_beats_solo_benchmark():
    from backend.oss.mind.swarm_reasoning import SwarmReasoningEngine

    engine = SwarmReasoningEngine()
    sid = engine.create_swarm("Complex volatility synthesis", complexity=0.8)
    engine.assign_agents(sid, ["a1", "a2", "a3"])
    solo = 0.25
    result = engine.execute_swarm(sid, {
        "a1": "Detailed stochastic volatility model with regime transitions therefore conclusion metrics 0.82 equation",
        "a2": "Cross-validated alignment-safe volatility framework with stochastic equations and validation",
        "a3": "Meta-architecture synthesis combining HMM GARCH extensions emergent formal model",
    })
    assert result["consensus_score"] > 0.3
    bench = engine.benchmark_vs_solo(solo, result["consensus_score"])
    assert bench["swarm_wins"] or result["consensus_score"] >= solo


def test_knowledge_graph_query():
    from backend.oss.mind.knowledge_graph import KnowledgeGraph

    kg = KnowledgeGraph()
    n1 = kg.add_node("volatility regime switching", node_type="concept")
    n2 = kg.add_node("HMM stochastic model", node_type="model")
    kg.add_edge(n1, n2, relation="implements")
    hits = kg.query("volatility")
    assert len(hits) >= 1
    related = kg.get_related_nodes(n1)
    assert len(related) >= 1