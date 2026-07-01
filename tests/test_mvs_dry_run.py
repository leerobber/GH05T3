"""MVS dry-run path — Phase 1 p95 gate (skip LLM)."""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


@pytest.fixture(autouse=True)
def _dry_run_env(monkeypatch):
    monkeypatch.setenv("MVS_DRY_RUN", "1")


def test_act_dry_run_skips_llm_and_is_fast():
    from backend.oss.omni_dna import create_omnidna
    from backend.oss.genomic_substrate import AgentHandle

    dna = create_omnidna("SCIENTIST", seed=99)
    handle = AgentHandle(genome_id=dna.genome_id, role="SCIENTIST", dna=dna)
    t0 = time.perf_counter()
    result = handle.act({"prompt": "test volatility model", "type": "analysis"})
    elapsed_ms = (time.perf_counter() - t0) * 1000

    assert result.get("fallback") is True
    assert "raw_output" in result
    assert elapsed_ms < 50, f"dry-run act() took {elapsed_ms:.1f}ms — gate is <50ms"


def test_act_dry_run_p95_batch():
    from backend.oss.omni_dna import create_omnidna
    from backend.oss.genomic_substrate import AgentHandle

    dna = create_omnidna("BUILDER", seed=7)
    handle = AgentHandle(genome_id=dna.genome_id, role="BUILDER", dna=dna)
    task = {"prompt": "summarize", "summary": "task"}
    times = []
    for _ in range(30):
        t0 = time.perf_counter()
        handle.act(task)
        times.append((time.perf_counter() - t0) * 1000)
    times.sort()
    p95 = times[int(len(times) * 0.95)]
    assert p95 < 50, f"p95={p95:.1f}ms exceeds 50ms gate"