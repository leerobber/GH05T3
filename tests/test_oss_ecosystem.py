"""OSS ecosystem FSM tests."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from oss.ecosystem.bootstrap import oss_bootstrap_plan
from oss.ecosystem.fsm import (
    EcosystemState,
    OmniEconomyState,
    OmniMindState,
    OssSpeciesState,
    ScientistStateOSS,
    ecosystem_fsm_spec,
    try_species_transition,
)
from oss.ecosystem.orchestrator import ecosystem_step, ecosystem_status
from oss.ecosystem.rewards import compute_ecosystem_rewards, reward_scientist_oss
from oss.ecosystem.store import load_ecosystem_state, save_ecosystem_state
from oss.kernel.agents import AgentRole
from oss.api.router import router as oss_router


def test_species_fsm_seven_states():
    spec = ecosystem_fsm_spec()
    states = spec["global_species"]["states"]
    assert len(states) == 7
    assert OssSpeciesState.S0_SPAWN.value in states
    assert OssSpeciesState.S6_EVOLVE.value in states


def test_role_scientist_six_states():
    spec = ecosystem_fsm_spec()
    sci = spec["roles"]["scientist"]
    assert ScientistStateOSS.R0_OBSERVE.value in sci["states"]
    assert ScientistStateOSS.R5_EVOLVE_DNA.value in sci["states"]
    assert "Memetic_Fitness" in sci["reward_formula"]


def test_omni_mind_and_economy_fsms():
    spec = ecosystem_fsm_spec()
    assert len(spec["omni_mind"]["states"]) == 7
    assert len(spec["omni_economy"]["states"]) == 6
    assert "Neuro-Coins" in str(spec["omni_economy"]["integrates"])


def test_species_transition_s0_to_s1():
    st = EcosystemState(species_state=OssSpeciesState.S0_SPAWN)
    ctx = {"agent_count": 5, "memories_ingested": 10, "pattern_score": 0.5,
           "artifacts_generated": True, "actions_count": 1, "rewards": {"aggregate": 0.5}}
    moved, fr, to = try_species_transition(st, ctx)
    assert moved
    assert to == OssSpeciesState.S1_PERCEIVE.value


def test_ecosystem_rewards():
    metrics = {
        "scientist": {"validity": 0.8, "novelty": 0.6, "downstream_impact": 0.5, "risk": 0.1, "memetic_fitness": 0.7},
        "builder": {"revenue": 50, "retention": 0.6, "trait_utilization": 0.5, "desire_fulfillment": 0.5, "harm_score": 0},
        "operator": {"uptime": 0.99, "efficiency": 0.9, "incident_severity": 0, "self_healing_success": 0.9},
        "investor": {"sharpe": 1.0, "treasury_growth": 0.2, "ecosystem_health": 0.7, "max_drawdown": 0.05, "volatility": 0.1},
        "governor": {"alignment_score": 0.9, "stability": 0.8, "safety": 0.95, "catastrophic_risk": 0},
        "omni_mind": {"goal_completion": 0.7, "swarm_efficiency": 0.8, "qualia_stability": 0.75, "knowledge_density": 0.6},
        "omni_economy": {"transaction_volume": 0.5, "trait_liquidity": 0.5, "memory_valuation": 0.4,
                         "desire_fulfillment_rate": 0.5, "soul_bond_strength": 0.5},
    }
    r = compute_ecosystem_rewards(metrics)
    assert r["aggregate"] > 0
    assert reward_scientist_oss(metrics["scientist"]) > 0.5


def test_ecosystem_step_runs():
    st = EcosystemState()
    out = ecosystem_step(st, domain="business", tick=1)
    assert "species" in out
    assert "omni_mind" in out
    assert "omni_economy" in out
    assert "rewards" in out


def test_bootstrap_five_phases():
    plan = oss_bootstrap_plan()
    assert len(plan["phases"]) == 5
    assert plan["current_phase"] == 1


def test_ecosystem_persistence(tmp_path, monkeypatch):
    import oss.ecosystem.store as store_mod
    monkeypatch.setattr(store_mod, "ECOSYSTEM_PATH", tmp_path / "eco.json")
    st = EcosystemState(generation=3, species_state=OssSpeciesState.S3_GENERATE)
    save_ecosystem_state(st)
    loaded = load_ecosystem_state()
    assert loaded.generation == 3
    assert loaded.species_state == OssSpeciesState.S3_GENERATE


def test_oss_ecosystem_api(tmp_path, monkeypatch):
    import oss.ecosystem.store as store_mod
    monkeypatch.setattr(store_mod, "ECOSYSTEM_PATH", tmp_path / "eco.json")
    monkeypatch.setattr(store_mod, "ECOSYSTEM_LOG_PATH", tmp_path / "eco.jsonl")
    app = FastAPI()
    app.include_router(oss_router, prefix="/oss")
    client = TestClient(app)
    assert client.get("/oss/oss/ecosystem").status_code == 200
    assert client.get("/oss/oss/ecosystem/fsm").status_code == 200
    assert client.get("/oss/oss/ecosystem/bootstrap").status_code == 200
    assert client.post("/oss/oss/ecosystem/step").status_code == 200


def test_kernel_fsm_includes_oss_species():
    from oss.kernel.state_machines import fsm_spec
    spec = fsm_spec()
    assert "oss_species" in spec
    assert spec["oss_species"]["global_species"]["loop"] == "S0→S1→S2→S3→S4→S5→S6→S1"