"""OSS living loop + substrate tests."""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from oss.architecture.diagram import architecture_spec
from oss.architecture.modules import module_breakdown
from oss.integration.living_loop import emerge_goals, living_loop_status, run_living_cycle
from oss.kernel.sandbox import reset_sandbox
from oss.substrate.genomic import query_genome
from oss.substrate.interaction_field import get_interaction_field
from oss.substrate.species_registry import get_species_registry
from oss.substrate.value_flow import get_value_flow
from oss.api.router import router as oss_router


def test_architecture_spec_has_layers():
    spec = architecture_spec()
    assert "omni_economy" in spec["layers_bottom_up"]
    assert "diagram_ascii" in spec
    assert len(spec["living_loop"]) == 6
    assert "omni_dna_to_mind" in spec["integration_hooks"]


def test_module_breakdown():
    mods = module_breakdown()
    assert "genomic_substrate" in mods["modules"]
    assert "living_loop" in mods["modules"]


def test_species_registry_five_roles():
    roles = get_species_registry().list_roles()
    assert len(roles) == 5
    names = {r["name"] for r in roles}
    assert "scientist" in names
    assert "governor" in names


def test_query_genome_by_capability():
    segs = query_genome(capability="scientific_theorizing")
    assert isinstance(segs, list)


def test_interaction_field_consensus():
    field = get_interaction_field()
    intent = field.publish_intent("research", "ORACLE", {"domain": "physics"})
    field.respond(intent.intent_id, agent="ORACLE", offer="hypothesis X", confidence=0.9)
    consensus = field.reach_consensus(intent.intent_id)
    assert consensus["winner"] == "ORACLE"


def test_value_flow_bounty():
    vf = get_value_flow()
    b = vf.create_bounty("test goal", 50.0)
    assert b.goal_id in vf.bounties


def test_emerge_goals_from_memory():
    goals = emerge_goals({"m1": "market instability treasury"})
    assert any("treasury" in g["description"].lower() for g in goals)


def test_living_cycle_runs():
    reset_sandbox()
    out = run_living_cycle(domain="business", tick=1, dry_run=True)
    assert len(out["role_actions"]) == 5
    assert "evolution" in out
    assert "omni_mind" in out
    assert "omni_economy" in out
    assert out["genomes_active"] >= 0
    assert len(out.get("spawned_agents", [])) == 5
    assert all("genome_id" in e for e in out["evolution"].values())


def test_living_loop_api():
    app = FastAPI()
    app.include_router(oss_router, prefix="/oss")
    client = TestClient(app)
    assert client.get("/oss/architecture").status_code == 200
    assert client.get("/oss/architecture/modules").status_code == 200
    assert client.get("/oss/living-loop").status_code == 200
    assert client.post("/oss/living-loop/run").status_code == 200
    assert client.get("/oss/substrate/genome?capability=infra_operations").status_code == 200