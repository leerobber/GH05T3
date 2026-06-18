from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from oss.dna.omni_dna import OmniDNA
from oss.dna.store import get_store
from oss.mind.omni_mind import get_mind
from oss.schemas.genome import SwarmTask

router = APIRouter(tags=["oss"])


class SwarmSolveRequest(BaseModel):
    problem: str = Field(..., min_length=3, max_length=4000)
    required_traits: list[str] = Field(default_factory=lambda: ["coding", "self_reflection"])
    max_agents: int = Field(default=3, ge=1, le=8)


class EvolveRequest(BaseModel):
    score: float = Field(default=0.75, ge=0.0, le=1.0)


@router.get("/health")
async def oss_health() -> dict[str, str]:
    return {"status": "ok", "layer": "oss", "version": "0.1.0"}


@router.get("/agents")
async def list_agents() -> dict[str, Any]:
    mind = get_mind()
    return mind.state()


@router.get("/agents/{genome_id}")
async def get_agent(genome_id: str) -> dict[str, Any]:
    store = get_store()
    dna = store.get(genome_id)
    if not dna:
        raise HTTPException(404, f"Genome {genome_id} not found")
    return dna.to_record().to_dict()


@router.post("/agents/{genome_id}/evolve")
async def evolve_agent(genome_id: str, body: EvolveRequest) -> dict[str, Any]:
    mind = get_mind()
    dna = mind.agents.get(genome_id) or get_store().get(genome_id)
    if not dna:
        raise HTTPException(404, f"Genome {genome_id} not found")
    deltas = dna.evolve(score=body.score)
    get_store().save(dna)
    mind.agents[dna.genome_id] = dna
    return {"genome_id": dna.genome_id, "trait_deltas": deltas, "traits": {
        k: round(t.value, 4) for k, t in dna.traits.items()
    }}


@router.get("/mind/state")
async def mind_state() -> dict[str, Any]:
    return get_mind().state()


@router.post("/swarm/solve")
async def swarm_solve(body: SwarmSolveRequest) -> dict[str, Any]:
    mind = get_mind()
    task = SwarmTask(
        problem=body.problem,
        required_traits=body.required_traits,
        max_agents=body.max_agents,
    )
    result = await mind.solve_with_swarm(task)
    return result.to_dict()


class DelegateRequest(BaseModel):
    task: str = Field(..., min_length=3, max_length=2000)
    agent: str = Field(default="SENTINEL", max_length=30)
    reward: int = Field(default=50, ge=0, le=1000)


@router.get("/economy/stats")
async def economy_stats() -> dict[str, Any]:
    from oss.adapters.sovereign import unified_economy_snapshot
    snap = unified_economy_snapshot()
    return snap.to_dict()


@router.get("/economy/unified")
async def economy_unified() -> dict[str, Any]:
    from oss.adapters.sovereign import unified_economy_snapshot
    return unified_economy_snapshot().to_dict()


@router.get("/mesh/status")
async def mesh_status() -> dict[str, Any]:
    from oss.grid.mesh import mesh_snapshot
    return mesh_snapshot().to_dict()


class MemoryRecallRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=2000)
    user_id: str = Field(default="default", max_length=64)
    top_k: int = Field(default=5, ge=1, le=20)


@router.get("/memory/status")
async def memory_status_endpoint() -> dict[str, Any]:
    from oss.adapters.memory import memory_status
    return memory_status()


@router.post("/memory/recall")
async def memory_recall(body: MemoryRecallRequest) -> dict[str, Any]:
    from oss.adapters.memory import recall_unified
    return await recall_unified(
        query=body.query,
        user_id=body.user_id,
        top_k=body.top_k,
    )


@router.post("/economy/delegate")
async def economy_delegate(body: DelegateRequest) -> dict[str, Any]:
    from oss.economy.neuro_coin import get_neuro_coin
    nc = get_neuro_coin()
    job_id = await nc.post_job(
        task=body.task,
        tags=[body.agent.upper()],
        reward=body.reward,
        posted_by="oss_api",
    )
    return {"job_id": job_id, "reward": body.reward, "tags": [body.agent.upper()]}


@router.post("/registry/sync")
async def registry_sync() -> dict[str, Any]:
    from oss.adapters.registry import sync_from_registry, sync_specialists_only
    store = get_store()
    stats = sync_from_registry(store)
    stats["specialists"] = sync_specialists_only(store)
    return stats


@router.get("/registry/status")
async def registry_status_endpoint() -> dict[str, Any]:
    from oss.adapters.registry import registry_status
    return registry_status(get_store())


class SettleRequest(BaseModel):
    customer_id: str = Field(..., min_length=1, max_length=128)
    amount_usd: float = Field(default=0.0, ge=0.0)
    plan: str = Field(default="starter", max_length=32)


@router.get("/monetization/status")
async def monetization_status() -> dict[str, Any]:
    from oss.monetization.stripe import settlement_status
    return settlement_status()


@router.post("/monetization/settle")
async def monetization_settle(body: SettleRequest) -> dict[str, Any]:
    from oss.monetization.stripe import settle_payment
    return settle_payment(
        body.customer_id,
        body.amount_usd,
        body.plan,
        "manual.test",
    )


class WorldSessionRequest(BaseModel):
    domain: str = Field(..., min_length=3, max_length=64)
    metadata: dict[str, Any] = Field(default_factory=dict)


@router.get("/world/domains")
async def world_domains() -> dict[str, Any]:
    from oss.world.runtime import list_domains
    return {"domains": list_domains()}


@router.post("/world/session")
async def world_start_session(body: WorldSessionRequest) -> dict[str, Any]:
    from oss.world.runtime import get_runtime, list_domains
    if body.domain not in list_domains():
        raise HTTPException(400, f"Unknown domain: {body.domain}")
    runtime = get_runtime()
    session = runtime.start_session(domain=body.domain, metadata=body.metadata)
    return runtime.snapshot(session.session_id)