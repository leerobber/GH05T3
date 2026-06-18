"""OSS Omni-Mind swarm tests."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from oss.dna.omni_dna import OmniDNA
from oss.dna.store import GenomeStore, SEED_TRAITS
from oss.mind.omni_mind import OmniMind
from oss.schemas.genome import SwarmTask, Trait


@pytest.fixture
def isolated_mind(tmp_path, monkeypatch):
    db = tmp_path / "genomes.db"
    monkeypatch.setattr("oss.dna.store._DB_PATH", db)
    monkeypatch.setattr("oss.dna.store._store", None)
    monkeypatch.setattr("oss.mind.omni_mind._mind", None)
    mind = OmniMind()
    mind.bootstrap()
    return mind


def test_select_agents_by_traits(isolated_mind):
    task = SwarmTask(
        problem="test",
        required_traits=["coding"],
        max_agents=2,
    )
    selected = isolated_mind.assign_swarm_task(task)
    assert len(selected) >= 1
    for gid in selected:
        dna = isolated_mind.agents[gid]
        assert dna.trait_value("coding") >= 0.5


@pytest.mark.anyio
async def test_solve_with_swarm_mock_llm(isolated_mind):
    mock_responses = [
        {"agent_id": "FORGE", "result": "Step 1: cache. Step 2: pool. Step 3: compress.", "provider": "test"},
    ]

    with patch("oss.adapters.swarm.invoke_agents_parallel", new_callable=AsyncMock) as mock_invoke:
        with patch("oss.adapters.swarm.publish_task", new_callable=AsyncMock):
            with patch("oss.adapters.evolution.record_swarm_cycle", return_value={"id": 42, "score": 0.8}):
                mock_invoke.return_value = mock_responses
                result = await isolated_mind.solve_with_swarm(SwarmTask(
                    problem="Reduce latency",
                    required_traits=["coding"],
                    max_agents=1,
                ))
    assert result.synthesis
    assert result.kairos_cycle_id == 42
    assert result.agents