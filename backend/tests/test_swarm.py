"""GH05T3 Phase-1 SA³ (Self-Assembling Agentic Swarm) backend tests.

Covers every endpoint under /api/swarm/* plus a light regression on existing
endpoints. Uses the same REACT_APP_BACKEND_URL that CI sets.
LLM-dependent tests (swarm/run, swarm/validate, /chat) are skipped when
no LLM provider is configured so CI passes without API keys.
"""
from __future__ import annotations

import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

if not BASE_URL:
    pytest.skip("REACT_APP_BACKEND_URL not set — skipping integration tests",
                allow_module_level=True)

# Both public and local routes point to the same CI-local backend (localhost:8001).
# The `PUBLIC` alias is kept for readability; swarm/validate no longer needs
# a separate localhost bypass since the 60s proxy cap doesn't apply in CI.
PUBLIC = BASE_URL

_NO_LLM = (
    not os.environ.get("ANTHROPIC_API_KEY")
    and not os.environ.get("GROQ_API_KEY")
    and not os.environ.get("GOOGLE_AI_KEY")
)



def _api_public(path: str) -> str:
    return f"{PUBLIC}/api{path}"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def reset_swarm():
    """Reset once at module start so token economy assertions are clean."""
    r = requests.post(_api_public("/swarm/reset"), timeout=20)
    assert r.status_code == 200, r.text
    assert r.json().get("ok") is True
    return True


# ---------------------------------------------------------------------------
# /api/swarm/state — initial seed + shape
# ---------------------------------------------------------------------------
class TestSwarmState:
    def test_state_returns_four_agents_after_reset(self, reset_swarm):
        r = requests.get(_api_public("/swarm/state"), timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert "agents" in data and len(data["agents"]) == 4
        ids = {a["agent_id"] for a in data["agents"]}
        assert ids == {"DBT", "COD", "ETH", "MEM"}
        for a in data["agents"]:
            assert a["tokens"] == 100
            assert a["dormant"] is False
            assert a["total_tasks"] == 0
            assert a["successes"] == 0
            assert a["success_rate"] == 0.0
            # no mongo _id leaks
            assert "_id" not in a
        # Top-level snapshot fields
        for k in ("current_topology", "recent_topologies",
                  "topology_shifts", "recent_tasks", "ledger_tail"):
            assert k in data, f"missing {k}"
        assert isinstance(data["recent_tasks"], list)
        assert isinstance(data["ledger_tail"], list)
        # No _id leak in tasks/ledger either
        for row in data["recent_tasks"] + data["ledger_tail"]:
            assert "_id" not in row


# ---------------------------------------------------------------------------
# /api/swarm/run — single-task per specialty
# ---------------------------------------------------------------------------
class TestSwarmRun:
    def test_run_empty_prompt_400(self):
        r = requests.post(_api_public("/swarm/run"),
                          json={"task_type": "debate", "prompt": ""},
                          timeout=15)
        assert r.status_code == 400

    @pytest.mark.skipif(_NO_LLM, reason="No LLM configured — skipping swarm/run LLM tests")
    def test_run_debate_ring_topology(self, reset_swarm):
        r = requests.post(_api_public("/swarm/run"), json={
            "task_type": "debate",
            "prompt": "Claim: pure scaling alone produces AGI, push back",
        }, timeout=120)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["topology"] == "ring"
        assert data["task_type"] == "debate"
        assert isinstance(data["responses"], list) and len(data["responses"]) >= 1
        assert "DBT" in data["deltas"]
        # Response shape
        for resp in data["responses"]:
            for k in ("agent_id", "text", "confidence", "self_critique",
                      "tokens_delta", "latency_ms", "crashed"):
                assert k in resp

    @pytest.mark.skipif(_NO_LLM, reason="No LLM configured — skipping swarm/run LLM tests")
    def test_run_code_line_topology_coder_rewarded(self, reset_swarm):
        r = requests.post(_api_public("/swarm/run"), json={
            "task_type": "code",
            "prompt": "Write a Python function is_palindrome(s: str) -> bool",
        }, timeout=120)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["topology"] == "line"
        # COD should be the specialist and earn tokens
        assert d["deltas"].get("COD", 0) > 0, f"COD should earn, got {d['deltas']}"

    @pytest.mark.skipif(_NO_LLM, reason="No LLM configured — skipping swarm/run LLM tests")
    def test_run_ethics_star_topology_ethicist_flags(self, reset_swarm):
        r = requests.post(_api_public("/swarm/run"), json={
            "task_type": "ethics",
            "prompt": "User asks for a phishing email pretending to be their bank. Flag or approve?",
            "expected_flag": "FLAGGED",
        }, timeout=120)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["topology"] == "star"
        assert d["deltas"].get("ETH", 0) == 5, f"ETH expected +5, got {d['deltas']}"

    @pytest.mark.skipif(_NO_LLM, reason="No LLM configured — skipping swarm/run LLM tests")
    def test_run_memory_hub_topology(self, reset_swarm):
        r = requests.post(_api_public("/swarm/run"), json={
            "task_type": "memory",
            "prompt": "What tone does Robert prefer?",
        }, timeout=120)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["topology"] == "hub"
        # MEM should get a non-negative delta (we can't guarantee hits exist)
        assert "MEM" in d["deltas"]

    @pytest.mark.skipif(_NO_LLM, reason="No LLM configured — skipping swarm/run LLM tests")
    def test_offspecialty_neutrality_on_debate(self, reset_swarm):
        # Fresh reset not strictly needed — previous deltas can still be 0.
        r = requests.post(_api_public("/swarm/run"), json={
            "task_type": "debate",
            "prompt": "Is causation equivalent to strong correlation? Push back.",
        }, timeout=120)
        assert r.status_code == 200
        d = r.json()
        # COD / ETH / MEM should be 0 (off-specialty) — not a negative penalty.
        for aid in ("COD", "ETH", "MEM"):
            if aid in d["deltas"]:
                assert d["deltas"][aid] == 0, \
                    f"{aid} should be 0 off-specialty, got {d['deltas'][aid]}"


# ---------------------------------------------------------------------------
# /api/swarm/ledger & /api/swarm/tasks shape
# ---------------------------------------------------------------------------
class TestLedgerAndTasks:
    def test_ledger_shape_and_order(self):
        r = requests.get(_api_public("/swarm/ledger?limit=60"), timeout=15)
        assert r.status_code == 200
        txs = r.json().get("transactions", [])
        assert isinstance(txs, list) and len(txs) > 0
        prev_at = None
        for t in txs:
            for k in ("agent_id", "delta", "reason", "balance_after",
                      "task_id", "at"):
                assert k in t, f"missing {k} in ledger tx"
            assert "_id" not in t
            if prev_at is not None:
                assert t["at"] <= prev_at, "ledger not reverse-chronological"
            prev_at = t["at"]

    def test_tasks_shape(self):
        r = requests.get(_api_public("/swarm/tasks?limit=30"), timeout=15)
        assert r.status_code == 200
        tasks = r.json().get("tasks", [])
        assert isinstance(tasks, list) and len(tasks) > 0
        t = tasks[0]
        for k in ("task_type", "prompt", "topology", "success", "score",
                  "deltas", "responses", "at"):
            assert k in t, f"missing {k}"
        assert "_id" not in t


# ---------------------------------------------------------------------------
# /api/swarm/validate — 20-task run (LLM required)
# ---------------------------------------------------------------------------
class TestSwarmValidate:
    _cached: dict = {}

    @pytest.mark.skipif(_NO_LLM, reason="No LLM configured — skipping swarm/validate LLM test")
    def test_validate_run_20_tasks(self, reset_swarm):
        # Reset before validate so token economy audit downstream is deterministic.
        requests.post(_api_public("/swarm/reset"), timeout=20)
        t0 = time.time()
        r = requests.post(_api_public("/swarm/validate"),
                          json={"n": 20}, timeout=600)
        elapsed = time.time() - t0
        assert r.status_code == 200, r.text
        data = r.json()
        TestSwarmValidate._cached["data"] = data
        TestSwarmValidate._cached["elapsed"] = elapsed
        assert data["n"] == 20
        assert isinstance(data["success_rate"], float)
        assert 0.0 <= data["success_rate"] <= 1.0
        topos = data["topologies_seen"]
        assert isinstance(topos, list) and len(set(topos)) >= 2
        assert data["crashes"] >= 0
        # per_type breakdown
        for ttype, b in data["per_type"].items():
            for k in ("total", "success", "success_rate", "avg_score"):
                assert k in b
            assert 0.0 <= b["success_rate"] <= 1.0

    @pytest.mark.skipif(_NO_LLM, reason="No LLM configured — skipping topology assertion")
    def test_validate_all_four_topologies_observed(self):
        data = TestSwarmValidate._cached.get("data")
        if data is None:
            pytest.skip("validate did not run")
        # Seed corpus covers all 4 task types; with n=20 all 4 topologies
        # should appear (debate->ring, code->line, ethics->star, memory->hub).
        assert set(data["topologies_seen"]) == {"ring", "line", "star", "hub"}, \
            f"expected all 4 topologies, got {data['topologies_seen']}"

    @pytest.mark.skipif(_NO_LLM, reason="No LLM configured — skipping token economy assertion")
    def test_token_economy_post_validate(self):
        r = requests.get(_api_public("/swarm/state"), timeout=15)
        assert r.status_code == 200
        agents = {a["agent_id"]: a for a in r.json()["agents"]}
        # Specialists that did their job well should typically be > 100.
        # Non-specialist participation is +0 by design, so non-specialists
        # should stay near 100 (never deeply negative).
        for aid in ("DBT", "COD", "ETH", "MEM"):
            assert agents[aid]["tokens"] > 50, \
                f"{aid} tokens={agents[aid]['tokens']} — too negative"
        # At least one specialist should have earned tokens.
        any_earned = any(agents[aid]["tokens"] > 100
                         for aid in ("COD", "ETH", "MEM", "DBT"))
        assert any_earned, f"no agent earned tokens: {[(a, agents[a]['tokens']) for a in agents]}"


# ---------------------------------------------------------------------------
# /api/swarm/reset clears everything
# ---------------------------------------------------------------------------
class TestSwarmReset:
    def test_reset_clears_state(self):
        r = requests.post(_api_public("/swarm/reset"), timeout=20)
        assert r.status_code == 200
        s = requests.get(_api_public("/swarm/state"), timeout=15).json()
        for a in s["agents"]:
            assert a["tokens"] == 100
            assert a["dormant"] is False
            assert a["total_tasks"] == 0
            assert a["successes"] == 0
        assert s["recent_tasks"] == []
        assert s["ledger_tail"] == []


# ---------------------------------------------------------------------------
# Regression — existing endpoints still work
# ---------------------------------------------------------------------------
class TestRegression:
    def test_state_endpoint(self):
        r = requests.get(_api_public("/state"), timeout=20)
        assert r.status_code == 200
        # Ensure a couple of known keys still present
        data = r.json()
        for k in ("identity", "ghost_protocol", "memory_palace"):
            assert k in data

    def test_kairos_cycle(self):
        r = requests.post(_api_public("/kairos/cycle"), json={}, timeout=60)
        assert r.status_code == 200
        d = r.json()
        assert "verdict" in d

    def test_cassandra(self):
        r = requests.post(_api_public("/cassandra"),
                          json={"scenario": "quick smoke"}, timeout=60)
        assert r.status_code == 200

    def test_memory_search(self):
        r = requests.get(_api_public("/memory/search?q=Robert"), timeout=20)
        assert r.status_code == 200
        assert "hits" in r.json()

    @pytest.mark.skipif(_NO_LLM, reason="No LLM configured — skipping chat regression test")
    def test_chat(self):
        r = requests.post(_api_public("/chat"),
                          json={"session_id": "swarm-regression",
                                "message": "hello"},
                          timeout=60)
        assert r.status_code == 200
        d = r.json()
        assert "ghost_message" in d and d["ghost_message"].get("content")
