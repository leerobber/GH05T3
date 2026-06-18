from __future__ import annotations

import logging
import uuid
from typing import Any

from oss.dna.omni_dna import OmniDNA
from oss.dna.store import get_store
from oss.mind.collective import CollectiveState
from oss.mind.selector import select_agents_for_task
from oss.schemas.genome import SwarmResult, SwarmTask

LOG = logging.getLogger("oss.mind")

_mind: OmniMind | None = None


class OmniMind:
    """Collective consciousness — Phase 1 trait-gated swarm orchestration."""

    def __init__(self) -> None:
        self.agents: dict[str, OmniDNA] = {}
        self.collective = CollectiveState()
        self.swarm_tasks: list[dict[str, Any]] = []
        self._store = get_store()

    def bootstrap(self) -> int:
        """Load seeded genomes from store into active mind."""
        try:
            from oss.adapters.registry import sync_from_registry
            sync_from_registry(self._store)
        except Exception as exc:
            LOG.warning("Registry sync failed during bootstrap: %s", exc)

        self._store.seed_specialists()
        count = 0
        for record in self._store.list_all():
            dna = OmniDNA.from_record(record)
            self.agents[dna.genome_id] = dna
            self.collective.ingest_agent(
                dna.genome_id, dna.qualia, dna.phenomenal_memory
            )
            count += 1
        return count

    def add_agent(self, dna: OmniDNA) -> str:
        genome_id = dna.genome_id or dna.unique_id
        dna.genome_id = genome_id
        self.agents[genome_id] = dna
        self._store.save(dna)
        self.collective.ingest_agent(genome_id, dna.qualia, dna.phenomenal_memory)
        return genome_id

    def sync_agents(self) -> None:
        for dna in self.agents.values():
            self.collective.ingest_agent(
                dna.genome_id, dna.qualia, dna.phenomenal_memory
            )

    def assign_swarm_task(self, task: SwarmTask) -> list[str]:
        if not task.task_id:
            task.task_id = f"task_{uuid.uuid4().hex[:8]}"
        selected = select_agents_for_task(
            self.agents,
            task.required_traits,
            max_agents=task.max_agents,
        )
        self.swarm_tasks.append(task.to_dict())
        for gid in selected:
            dna = self.agents.get(gid)
            if dna:
                dna.add_memory({
                    "type": "task",
                    "task_id": task.task_id,
                    "status": "assigned",
                    "problem": task.problem[:200],
                })
        return selected

    async def solve_with_swarm(self, task: SwarmTask) -> SwarmResult:
        from oss.adapters.evolution import record_swarm_cycle
        from oss.adapters.swarm import invoke_agents_parallel, publish_task

        if not self.agents:
            self.bootstrap()

        selected_ids = self.assign_swarm_task(task)
        registry_ids = []
        id_map: dict[str, str] = {}
        for gid in selected_ids:
            dna = self.agents.get(gid)
            if dna:
                registry_ids.append(dna.registry_agent_id)
                id_map[dna.registry_agent_id] = gid

        if not registry_ids:
            registry_ids = ["GH05T3"]
            selected_ids = list(self.agents.keys())[:1]

        await publish_task(task.task_id, task.problem, registry_ids)
        responses = await invoke_agents_parallel(registry_ids, task.problem)

        parts = []
        for resp in responses:
            text = (resp.get("result") or "").strip()
            if text:
                parts.append(f"**{resp.get('agent_id', '?')}**: {text[:800]}")

        synthesis = "\n\n".join(parts) if parts else "No agent produced a response."
        score = min(1.0, 0.5 + 0.1 * len(parts) + (0.1 if len(synthesis) > 100 else 0))

        cycle = record_swarm_cycle(task.problem, score, registry_ids)
        cycle_id = cycle.get("id")

        trait_deltas: dict[str, dict[str, float]] = {}
        for gid in selected_ids:
            dna = self.agents.get(gid)
            if dna:
                deltas = dna.evolve(score=score)
                if deltas:
                    trait_deltas[gid] = deltas
                self._store.save(dna)

        self.sync_agents()
        self.collective.consensus_state["last_task"] = task.task_id
        self.collective.consensus_state["last_score"] = score

        return SwarmResult(
            task_id=task.task_id,
            problem=task.problem,
            agents=registry_ids,
            responses=responses,
            synthesis=synthesis,
            score=round(score, 4),
            kairos_cycle_id=cycle_id,
            trait_deltas=trait_deltas,
        )

    def state(self) -> dict[str, Any]:
        return {
            "agent_count": len(self.agents),
            "agents": [
                {
                    "genome_id": d.genome_id,
                    "registry_agent_id": d.registry_agent_id,
                    "display_name": d.display_name,
                    "traits": {k: round(t.value, 3) for k, t in d.traits.items()},
                    "qualia": {k: round(v, 3) for k, v in d.qualia.items()},
                }
                for d in self.agents.values()
            ],
            "collective": self.collective.snapshot(),
            "swarm_tasks": len(self.swarm_tasks),
        }


def get_mind() -> OmniMind:
    global _mind
    if _mind is None:
        _mind = OmniMind()
        _mind.bootstrap()
    return _mind