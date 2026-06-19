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


class WorldStepRequest(BaseModel):
    action: dict[str, Any] = Field(default_factory=dict)


@router.get("/world/session/{session_id}")
async def world_session_snapshot(session_id: str) -> dict[str, Any]:
    from oss.world.runtime import get_runtime
    runtime = get_runtime()
    try:
        return runtime.snapshot(session_id)
    except KeyError:
        raise HTTPException(404, f"Session {session_id} not found")


@router.post("/world/session/{session_id}/step")
async def world_session_step(session_id: str, body: WorldStepRequest) -> dict[str, Any]:
    from oss.world.runtime import get_runtime
    runtime = get_runtime()
    try:
        await runtime.step(session_id, action=body.action)
    except KeyError:
        raise HTTPException(404, f"Session {session_id} not found")
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return runtime.snapshot(session_id)


# ── Omni Forge — agency training layer ────────────────────────────────────────

class ForgeSubmitRequest(BaseModel):
    domain: str = Field(..., min_length=3, max_length=64)
    user: str = Field(..., min_length=10, max_length=4000)
    assistant: str = Field(..., min_length=20, max_length=8000)
    system: str = Field(default="", max_length=2000)
    genome_id: str = Field(default="gh05t3", max_length=64)


class ForgeCycleRequest(BaseModel):
    include_pipeline: bool = True
    include_seeds: bool = True
    min_tier: str = Field(default="silver", max_length=16)
    export: bool = True


@router.get("/forge/status")
async def forge_status() -> dict[str, Any]:
    from oss.adapters.forge import forge_status
    return forge_status()


@router.post("/forge/cycle")
async def forge_cycle(body: ForgeCycleRequest) -> dict[str, Any]:
    from oss.forge.schemas import QualityTier
    from oss.adapters.forge import trigger_forge_cycle
    try:
        tier = QualityTier(body.min_tier.lower())
    except ValueError:
        raise HTTPException(400, f"Unknown tier: {body.min_tier}")
    return trigger_forge_cycle(
        include_pipeline=body.include_pipeline,
        include_seeds=body.include_seeds,
        min_tier=tier,
        export=body.export,
    )


@router.post("/forge/submit")
async def forge_submit(body: ForgeSubmitRequest) -> dict[str, Any]:
    from oss.forge.agency import get_agency
    from oss.forge.domains import resolve_domain
    domain = resolve_domain(body.domain)
    return get_agency().submit_and_curate(
        domain=domain,
        user=body.user,
        assistant=body.assistant,
        system=body.system,
        genome_id=body.genome_id,
    )


@router.get("/forge/preflight")
async def forge_preflight() -> dict[str, Any]:
    from oss.forge.train_bridge import preflight_report
    return preflight_report()


@router.get("/forge/domains")
async def forge_domains_list(q: str = "") -> dict[str, Any]:
    from oss.forge.domains import list_domains, search_domains
    items = search_domains(q) if q else list_domains()
    return {"domains": items, "count": len(items)}


@router.get("/forge/elite/profile")
async def forge_elite_profile() -> dict[str, Any]:
    from pathlib import Path
    import json
    manifest = Path(__file__).resolve().parents[2] / "backend" / "data" / "training" / "forge_elite_manifest.json"
    if not manifest.exists():
        return {"status": "no_elite_export", "paradigm": "omni_strand_sft"}
    return json.loads(manifest.read_text(encoding="utf-8"))


@router.post("/forge/elite/export")
async def forge_elite_export(min_tier: str = "gold") -> dict[str, Any]:
    from oss.forge.elite_train import export_elite_strands
    from oss.forge.schemas import QualityTier
    try:
        tier = QualityTier(min_tier.lower())
    except ValueError:
        raise HTTPException(400, f"Unknown tier: {min_tier}")
    return export_elite_strands(min_tier=tier)


class ForgeRouteRequest(BaseModel):
    text: str = Field(..., min_length=3, max_length=8000)
    task_domain: str = Field(default="", max_length=64)
    session_id: str = Field(default="", max_length=64)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)


@router.get("/train/agents")
async def train_agents_list() -> dict[str, Any]:
    from oss.train.agents import list_agents
    return {"agents": list_agents(), "trainer": "sovereign_loop"}


@router.get("/train/constitution")
async def train_constitution() -> dict[str, Any]:
    from oss.train.constitution import constitution_report
    return constitution_report()


class TrainRunRequest(BaseModel):
    agent_id: str = Field(default="GH05T3", max_length=32)
    steps: int = Field(default=80, ge=10, le=5000)
    model_id: str = Field(default="Qwen/Qwen2.5-Coder-3B-Instruct", max_length=128)
    forge_only: bool = True
    dry_run: bool = False


@router.post("/train/run")
async def train_run(body: TrainRunRequest) -> dict[str, Any]:
    """Sovereign Train Kernel — agent-native, no TRL."""
    from pathlib import Path
    from oss.train.engine import run_training
    from oss.train.schemas import TrainConfig, TrainJob, TrainSource

    sources = [TrainSource.FORGE, TrainSource.ELITE] if body.forge_only else [TrainSource.ALL]
    job = TrainJob(
        agent_id=body.agent_id,
        dry_run=body.dry_run,
        config=TrainConfig(
            model_id=body.model_id,
            max_steps=body.steps,
            sources=sources,
        ),
    )
    try:
        return run_training(job).to_dict()
    except Exception as exc:
        raise HTTPException(500, str(exc))


@router.post("/forge/route")
async def forge_route_plan(body: ForgeRouteRequest) -> dict[str, Any]:
    """Preview Omni MoE inference routing (spectral classify + holographic context)."""
    from oss.forge.inference_router import plan_inference_route
    messages = [{"role": "user", "content": body.text}]
    route = plan_inference_route(
        messages,
        task_domain=body.task_domain,
        session_id=body.session_id,
        base_temperature=body.temperature,
    )
    return {
        "route": route.to_dict(),
        "adapter_bucket": route.adapter_bucket,
        "scaled_temperature": route.scaled_temperature,
        "novel_methods": route.novel_methods,
    }


# ── MVS bridge (canonical gateway mount) ──────────────────────────────────────

class MvsCycleRequest(BaseModel):
    cycles: int = Field(default=1, ge=1, le=50)
    dry_run: bool = True


class OmniRouteRequest(BaseModel):
    prompt: str = Field(default="", max_length=8000)


@router.get("/mvs/status")
async def mvs_status() -> dict[str, Any]:
    from backend.oss.loop import ensure_mvs_seeded, load_oss
    from backend.oss.mvs import get_mvs

    ensure_mvs_seeded(verbose=False)
    mvs = get_mvs()
    sub = mvs["substrate"]
    genomes = getattr(sub, "genomes", {})
    roles = sorted({v.role for v in genomes.values()}) if genomes else []
    avg_fitness = (
        sum(getattr(v, "fitness", 0.5) for v in genomes.values()) / len(genomes)
        if genomes else 0.0
    )
    oss = load_oss()
    rewards = oss.get("rewards", {})
    return {
        "available": True,
        "genomes": {
            "total_genomes": len(genomes),
            "roles": roles,
            "avg_fitness": round(avg_fitness, 4),
        },
        "mind": {"memories": 0},
        "economy_balances_sample": {},
        "loop_state": {
            "species": oss.get("species_state", "S5_evolve"),
            "aggregate": float(rewards.get("aggregate", 0.65)),
            "omni_mind": float(rewards.get("omni_mind", 0.62)),
        },
        "source": "backend.oss.mvs + oss_ecosystem.json",
    }


@router.post("/mvs/cycle")
async def mvs_cycle(body: MvsCycleRequest) -> dict[str, Any]:
    import time
    from backend.oss.loop import ensure_mvs_seeded, run_cycle

    ensure_mvs_seeded(verbose=False)
    t0 = time.monotonic()
    results = []
    for i in range(body.cycles):
        cl = run_cycle(i, dry_run=body.dry_run, verbose=False)
        results.append({
            "tick": cl.tick,
            "global": cl.global_state,
            "agg": cl.rewards.get("aggregate", 0.0),
            "omni_mind": cl.rewards.get("omni_mind", 0.0),
        })
    return {
        "ran": body.cycles,
        "dry_run": body.dry_run,
        "results": results,
        "duration_sec": round(time.monotonic() - t0, 3),
        "note": "cycles executed via backend.oss.loop (MVS only)",
    }


@router.post("/omni/route")
async def omni_route(body: OmniRouteRequest) -> dict[str, Any]:
    """Richer MoE routing alias used by gateway consumers and smoke tests."""
    from oss.forge.inference_router import plan_inference_route

    messages = [{"role": "user", "content": body.prompt or "route"}]
    try:
        route = plan_inference_route(messages)
        return {
            "route": route.to_dict(),
            "adapter_bucket": route.adapter_bucket,
            "scaled_temperature": route.scaled_temperature,
            "novel_methods": route.novel_methods,
        }
    except Exception as exc:
        return {"error": str(exc), "route": "degraded"}