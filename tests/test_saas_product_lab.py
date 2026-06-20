"""SaaS product design lab + domain_research adapter wiring tests."""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from oss.forge.lab_inference import adapter_on_disk, lab_inference_status
from oss.forge.moe_farm import (
    ADAPTER_BUCKETS,
    adapter_bucket_for_agent_role,
    resolve_legacy_adapter_bucket,
    resolve_adapter_path_for_bucket,
)
from oss.forge.inference_router import plan_inference_route
from oss.lab.saas_product import (
    ProductDesigner,
    ProductEvaluator,
    load_lab_data,
    run_old_stack_lab,
    run_oss_saas_lab,
    saas_lab_comparison,
    score_product,
)
from oss.lab.metrics import make_log_entry, logs_to_dataframe, compute_collective_metrics
from oss.substrate.genomic import reset_genomic_substrate
from oss.api.router import router as oss_router


def test_business_bucket_maps_domain_research_adapter():
    assert "business" in ADAPTER_BUCKETS
    assert ADAPTER_BUCKETS["business"] == "domain_research_adapter"
    assert resolve_legacy_adapter_bucket("business") == "business"
    assert adapter_bucket_for_agent_role("builder") == "business"
    assert adapter_bucket_for_agent_role("investor") == "business"


def test_adapter_path_for_business_exists():
    base = _ROOT / "backend" / "models"
    bucket, path = resolve_adapter_path_for_bucket(base, "business")
    assert bucket == "business"
    assert (path / "adapter_config.json").exists()


def test_inference_route_uses_business_bucket():
    route = plan_inference_route(
        [{"role": "user", "content": "Design a SaaS product for SMB founders"}],
        task_domain="business",
    )
    assert route.adapter_bucket == "business"
    assert "legacy_adapter_bucket" in route.novel_methods


def test_lab_data_loads():
    users, market = load_lab_data()
    assert len(users) >= 4
    assert "competitors" in market


def test_old_stack_product_lab():
    result = run_old_stack_lab(seed=3)
    assert result.product["name"] == "SynthFlow"
    assert 0 <= result.score <= 1


def test_score_product_shared_evaluator():
    users, market = load_lab_data()
    product = ProductDesigner(users, market).propose_product()
    s1 = score_product(product, users, market)
    s2 = ProductEvaluator(users, market).score_product(product)
    assert s1 == s2


def test_oss_saas_lab_runs():
    reset_genomic_substrate()
    out = run_oss_saas_lab(seed=3, dry_run=True, cycles=3, use_adapter=False)
    assert out["stack"] == "oss_genomic_substrate"
    assert out["cycles"] == 3
    assert out["cycles_detail"]
    assert out["logs_written"] >= 3
    assert adapter_on_disk("business")


def test_saas_lab_comparison():
    reset_genomic_substrate()
    cmp = saas_lab_comparison(seed=3, dry_run=True, cycles=2, use_adapter=False)
    assert cmp["problem"]
    assert cmp["old_stack"]["stack"] == "old_files_classes_api"
    assert cmp["oss_stack"]["stack"] == "oss_genomic_substrate"


def test_metrics_schema():
    entry = make_log_entry(
        cycle=0,
        agent_id="NEXUS",
        role="builder",
        traits={"creativity": 0.7},
        fitness=0.65,
        neurocoins=50.0,
        proposal={"name": "TestSaaS"},
        score=0.72,
        events=["mutation"],
    )
    df = logs_to_dataframe([entry])
    assert "trait_creativity" in df.columns
    collective = compute_collective_metrics([entry])
    assert collective["agents"] == 1


def test_lab_api_routes():
    app = FastAPI()
    app.include_router(oss_router, prefix="/oss")
    client = TestClient(app)
    assert client.get("/oss/lab/inference").status_code == 200
    assert client.get("/oss/lab/saas-product?cycles=2&use_adapter=false").status_code == 200
    assert client.get("/oss/lab/saas-product/metrics").status_code == 200


def test_lab_inference_status():
    status = lab_inference_status()
    assert status["bucket"] == "business"
    assert status["adapter_on_disk"] is True