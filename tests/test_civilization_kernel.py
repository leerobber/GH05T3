"""Civilization Kernel tests."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from oss.kernel.agents import (
    AGENT_REGISTRY,
    AgentRole,
    AgentStage,
    agent_for_phase,
    shards_for_agent_stage,
    stage_spec,
)
from oss.kernel.data_territory import TERRITORIES, list_territories, territory_for_tick
from oss.kernel.governance import authorize_action, preflight
from oss.kernel.heartbeat import kernel_status, tick
from oss.kernel.schemas import HeartbeatPhase, TreasuryPolicy
from oss.kernel.schemas import KernelState
from oss.kernel.shards import ROLE_PRIMARY_SHARDS, ShardType
from oss.kernel.collaboration import collaboration_overview, run_collaboration_loop
from oss.kernel.orchestrator import orchestrator_step, orchestrator_status
from oss.kernel.rewards import compute_all_rewards, reward_scientist
from oss.kernel.sandbox import SandboxEnvironment, reset_sandbox
from oss.kernel.state_machines import (
    CycleMachineState,
    GlobalCycleState,
    fsm_spec,
    try_global_transition,
)
from oss.kernel.prompts import v1_implementation_plan
from oss.kernel.store import load_state, load_training_progress, save_state, save_training_progress
from oss.kernel.training_schedule import (
    GlobalPhase,
    TrainingProgress,
    evaluate_role_unlock,
    record_eval,
    schedule_overview,
)
from oss.forge.moe_farm import adapter_bucket_for_agent_role
from oss.api.router import router as oss_router


def test_four_pillars_in_status():
    status = kernel_status()
    assert "theory_engine" in status["pillars"]
    assert "finance_engine" in status["pillars"]
    assert "operations_engine" in status["pillars"]
    assert "constitution_engine" in status["pillars"]


def test_five_agents_three_stages_each():
    assert len(AGENT_REGISTRY) == 5
    for role in AgentRole:
        spec = AGENT_REGISTRY[role]
        assert len(spec.stages) == 3
        stages = [s.stage for s in spec.stages]
        assert AgentStage.BASE in stages
        assert AgentStage.SPECIALIST in stages
        assert AgentStage.FRONTIER in stages


def test_role_primary_shard_mapping():
    assert ShardType.WORLD_MODEL in ROLE_PRIMARY_SHARDS["scientist"]
    assert ShardType.MARKETS in ROLE_PRIMARY_SHARDS["investor"]
    assert ShardType.AGENCY_TOOLS in ROLE_PRIMARY_SHARDS["operator"]
    assert ShardType.GOVERNANCE in ROLE_PRIMARY_SHARDS["governor"]
    assert ShardType.OPERATIONS in ROLE_PRIMARY_SHARDS["builder"]


def test_governor_frontier_meta_alignment():
    frontier = stage_spec(AgentRole.GOVERNOR, AgentStage.FRONTIER)
    assert frontier is not None
    assert ShardType.META_ALIGNMENT in frontier.shards
    assert ShardType.CROSS_ROLE in frontier.shards


def test_phase_agent_mapping():
    assert agent_for_phase(HeartbeatPhase.RESEARCH) == AgentRole.SCIENTIST
    assert agent_for_phase(HeartbeatPhase.GOVERN) == AgentRole.GOVERNOR
    assert agent_for_phase(HeartbeatPhase.MONETIZE) == AgentRole.BUILDER


def test_moe_agent_role_buckets():
    assert adapter_bucket_for_agent_role("scientist") == "research"
    assert adapter_bucket_for_agent_role("investor") == "business"
    assert adapter_bucket_for_agent_role("governor") == "security"


def test_status_includes_agents():
    status = kernel_status()
    assert status["agent_count"] == 5
    assert len(status["agents"]) == 5
    roles = {a["agent"] for a in status["agents"]}
    assert roles == {"scientist", "investor", "operator", "governor", "builder"}


def test_scientist_specialist_shards():
    shards = shards_for_agent_stage(AgentRole.SCIENTIST, AgentStage.SPECIALIST)
    keys = {s["key"] for s in shards}
    assert "scientific_text" in keys
    assert "simulation" in keys


def test_data_territories_cover_unknown():
    keys = {t.key for t in TERRITORIES}
    assert "physics" in keys
    assert "frontier_unknown" in keys
    assert "sensor_raw" in keys
    assert len(list_territories()) >= 15


def test_territory_rotation():
    t0 = territory_for_tick(1)
    t1 = territory_for_tick(2)
    assert t0.key != t1.key or len(TERRITORIES) == 1


def test_governance_blocks_human_gate():
    ok, _ = authorize_action("wire_real_funds")
    assert not ok


def test_dry_run_tick_completes():
    result = tick(dry_run=True)
    assert result.tick >= 1
    assert len(result.phases) >= 6
    assert not result.blocked
    phase_names = {p.phase.value for p in result.phases}
    assert "research" in phase_names
    assert "govern" in phase_names


def test_treasury_policy_sums_to_one():
    TreasuryPolicy().validate()
    with pytest.raises(ValueError):
        TreasuryPolicy(reserve_pct=0.5, research_pct=0.5, compute_pct=0.5).validate()


def test_kernel_api_routes():
    app = FastAPI()
    app.include_router(oss_router, prefix="/oss")
    client = TestClient(app)
    assert client.get("/oss/kernel/status").status_code == 200
    assert client.get("/oss/kernel/territories").status_code == 200
    assert client.get("/oss/kernel/agents").status_code == 200
    assert client.get("/oss/kernel/agents?role=governor").status_code == 200
    assert client.get("/oss/kernel/shards").status_code == 200
    assert client.get("/oss/kernel/shards?role=scientist&stage=frontier").status_code == 200
    resp = client.post("/oss/kernel/tick", json={"dry_run": True, "ticks": 1})
    assert resp.status_code == 200
    assert resp.json().get("all_ok") is True


def test_training_schedule_four_phases():
    sched = schedule_overview()
    phases = [p["phase"] for p in sched["phases"]]
    assert GlobalPhase.FOUNDATION.value in phases
    assert GlobalPhase.FRONTIER.value in phases
    assert len(phases) == 4


def test_foundation_unlock_requires_all_gates():
    progress = TrainingProgress()
    rp = progress.roles["scientist"]
    eval_out = evaluate_role_unlock(AgentRole.SCIENTIST, rp)
    assert not eval_out["unlocked"]
    assert eval_out["global_phase"] == GlobalPhase.FOUNDATION.value


def test_role_advance_with_governor_approval(tmp_path, monkeypatch):
    import oss.kernel.store as store_mod
    monkeypatch.setattr(store_mod, "TRAINING_PATH", tmp_path / "training.json")
    progress = TrainingProgress(global_phase=GlobalPhase.ROLE_SPECIALIZATION)
    for r in AgentRole:
        progress.roles[r.value].global_phase = GlobalPhase.ROLE_SPECIALIZATION
    progress.roles["scientist"].metrics = {
        "concept_accuracy": 0.85,
        "experiment_coherence": 0.80,
        "no_hallucinated_equations": 1.0,
    }
    result = record_eval(
        progress, role="scientist",
        metrics={},
        governor_approved=True,
    )
    assert result["evaluations"][0]["all_metrics_pass"]
    save_training_progress(progress)


def test_collaboration_six_steps():
    loop = run_collaboration_loop(tick=1, domain="business", territory="physics")
    assert len(loop["steps"]) == 6
    steps = [s["step"] for s in loop["steps"]]
    assert steps[0] == "scientist_propose"
    assert steps[-1] == "training_feedback"


def test_collaboration_overview():
    overview = collaboration_overview()
    assert len(overview["steps"]) == 6


def test_tick_includes_collaboration():
    result = tick(dry_run=True)
    improve = next(p for p in result.phases if p.phase.value == "improve")
    assert "collaboration" in improve.metrics
    assert len(improve.metrics["collaboration"]["steps"]) == 6


def test_status_includes_training_schedule():
    status = kernel_status()
    assert "training_schedule" in status
    assert "training_progress" in status
    assert len(status["training_schedule"]["phases"]) == 4


def test_fsm_spec_global_states():
    spec = fsm_spec()
    states = spec["global_cycle"]["states"]
    assert GlobalCycleState.S0_IDEATION.value in states
    assert GlobalCycleState.S5_EVALUATION.value in states
    assert len(spec["roles"]) == 5


def test_global_transition_s0_to_s1():
    st = CycleMachineState()
    ctx = {"feasibility": 0.8, "alignment": 0.9}
    moved, fr, to = try_global_transition(st, ctx)
    assert moved
    assert to == GlobalCycleState.S1_DESIGN.value


def test_sandbox_produces_reward_metrics():
    reset_sandbox()
    env = SandboxEnvironment()
    m = env.run_cycle(domain="business", tick=1)
    rewards = compute_all_rewards(m)
    assert "scientist" in m
    assert "aggregate" in rewards
    assert -1.0 <= rewards["aggregate"] <= 2.0


def test_reward_scientist_formula():
    r = reward_scientist(validity=1.0, downstream_impact=1.0, risk=0.0)
    assert r > 0.5


def test_orchestrator_step_advances():
    reset_sandbox()
    st = CycleMachineState()
    out = orchestrator_step(st, domain="growth", tick=1)
    assert "global_state" in out
    assert "rewards" in out
    assert out["active_agent"] in {"scientist", "builder", "operator", "investor", "governor"}


def test_v1_plan_seven_steps():
    plan = v1_implementation_plan()
    assert len(plan["steps"]) == 7


def test_tick_includes_orchestrator():
    result = tick(dry_run=True)
    improve = next(p for p in result.phases if p.phase.value == "improve")
    assert "orchestrator" in improve.metrics


def test_kernel_fsm_api_routes(tmp_path, monkeypatch):
    import oss.kernel.store as store_mod
    monkeypatch.setattr(store_mod, "CYCLE_PATH", tmp_path / "cycle.json")
    monkeypatch.setattr(store_mod, "CYCLE_LOG_PATH", tmp_path / "cycle.jsonl")
    app = FastAPI()
    app.include_router(oss_router, prefix="/oss")
    client = TestClient(app)
    assert client.get("/oss/kernel/fsm").status_code == 200
    assert client.get("/oss/kernel/orchestrator").status_code == 200
    assert client.get("/oss/kernel/v1-plan").status_code == 200
    assert client.get("/oss/kernel/sandbox").status_code == 200
    assert client.post("/oss/kernel/orchestrator/step").status_code == 200


def test_kernel_training_api_routes(tmp_path, monkeypatch):
    import oss.kernel.store as store_mod
    monkeypatch.setattr(store_mod, "TRAINING_PATH", tmp_path / "training.json")
    app = FastAPI()
    app.include_router(oss_router, prefix="/oss")
    client = TestClient(app)
    assert client.get("/oss/kernel/training/schedule").status_code == 200
    assert client.get("/oss/kernel/training/progress").status_code == 200
    assert client.get("/oss/kernel/collaboration").status_code == 200
    resp = client.post(
        "/oss/kernel/training/eval",
        json={"role": "governor", "metrics": {"violation_detection": 0.90}},
    )
    assert resp.status_code == 200


def test_state_persistence_roundtrip(tmp_path, monkeypatch):
    import oss.kernel.store as store_mod
    monkeypatch.setattr(store_mod, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(store_mod, "LOG_PATH", tmp_path / "ticks.jsonl")
    s = KernelState(tick=42, last_domain="frontier")
    save_state(s)
    loaded = load_state()
    assert loaded.tick == 42
    assert loaded.last_domain == "frontier"