"""Sovereign Train Kernel tests."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from oss.train.agents import resolve_agent, list_agents
from oss.train.constitution import (
    LOSS_CEILING,
    LOSS_FLOOR,
    RULES,
    assert_final_loss,
    assert_loss_healthy,
    constitution_report,
)
from oss.train.dataset import build_examples
from oss.train.schemas import TrainSource
from oss.train.tokenize import tokenize_supervised
from oss.api.router import router as oss_router


def test_constitution_has_six_rules():
    assert len(RULES) >= 6
    assert any("TRL" in r for r in RULES)
    assert any("fp16" in r for r in RULES)


def test_constitution_loss_bounds():
    assert_loss_healthy(2.5, step=1)
    with pytest.raises(Exception):
        assert_loss_healthy(0.0, step=5)
    with pytest.raises(Exception):
        assert_final_loss(15.0)
    assert_final_loss(3.2)


def test_agent_registry_lists_six():
    agents = list_agents()
    ids = {a["agent_id"] for a in agents}
    assert "GH05T3" in ids
    assert "FORGE" in ids
    assert "SENTINEL" in ids


def test_resolve_forge_agent():
    p = resolve_agent("FORGE")
    assert p.adapter_dir == "code_adapter"


def test_build_forge_dataset_for_gh05t3():
    examples, manifest = build_examples(
        "GH05T3",
        [TrainSource.FORGE, TrainSource.ELITE],
        seed=42,
    )
    assert len(examples) >= 5
    assert manifest["agent_id"] == "GH05T3"
    assert "forge_gold" in manifest["by_source"] or "elite_strand" in manifest["by_source"]


def test_tokenize_masks_prompt():
    class FakeTok:
        pad_token_id = 0
        eos_token_id = 0

        def encode(self, text, add_special_tokens=False, truncation=False, max_length=None):
            ids = list(range(len(text.split())))
            if truncation and max_length:
                return ids[:max_length]
            return ids

    text = (
        "<|im_start|>system\nsys<|im_end|>\n"
        "<|im_start|>user\nhi<|im_end|>\n"
        "<|im_start|>assistant\nhello<|im_end|>"
    )
    tok = FakeTok()
    ex = tokenize_supervised(tok, text, max_seq_len=128)
    assert ex is not None
    assert -100 in ex.labels
    assert any(l != -100 for l in ex.labels)


def test_train_constitution_api():
    app = FastAPI()
    app.include_router(oss_router, prefix="/oss")
    client = TestClient(app)
    resp = client.get("/oss/train/constitution")
    assert resp.status_code == 200
    assert "rules" in resp.json()


def test_train_agents_api():
    app = FastAPI()
    app.include_router(oss_router, prefix="/oss")
    client = TestClient(app)
    resp = client.get("/oss/train/agents")
    assert resp.status_code == 200
    assert resp.json()["trainer"] == "sovereign_loop"


def test_constitution_report_structure():
    report = constitution_report()
    assert "rules" in report
    assert LOSS_FLOOR == 0.3
    assert LOSS_CEILING == 10.0