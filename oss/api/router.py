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


class BMECycleRequest(BaseModel):
    cycles: int = Field(default=1, ge=1, le=1000)
    target_universe: int | None = Field(default=None, ge=0, le=7)
    allow_migration: bool = True
    allow_promotion: bool = True
    allow_breakthrough: bool = True
    push_sovereign_core: bool = False


@router.get("/mvs/status")
async def mvs_status() -> dict[str, Any]:
    try:
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
    except ModuleNotFoundError:
        return {
            "available": True,
            "genomes": {"total_genomes": 0, "roles": [], "avg_fitness": 0.0},
            "mind": {"memories": 0},
            "economy_balances_sample": {},
            "loop_state": {"species": "S0_perceive", "aggregate": 0.0, "omni_mind": 0.0},
            "source": "backend.oss.mvs + oss_ecosystem.json",
        }


@router.get("/metrics")
async def oss_metrics():
    """Prometheus metrics for MVS cycle and marketplace signals."""
    from starlette.responses import JSONResponse, Response

    from oss.observability.metrics import metrics_payload

    body, media_type = metrics_payload()
    if media_type == "application/json":
        return JSONResponse(body)
    return Response(content=body, media_type=media_type)


@router.post("/mvs/cycle")
async def mvs_cycle(body: MvsCycleRequest) -> dict[str, Any]:
    import time

    from oss.observability.metrics import record_cycle

    try:
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
        duration = time.monotonic() - t0
        record_cycle(duration, dry_run=body.dry_run, outcome="ok")
        return {
            "ran": body.cycles,
            "dry_run": body.dry_run,
            "results": results,
            "duration_sec": round(duration, 3),
            "note": "cycles executed via backend.oss.loop (MVS only)",
        }
    except ModuleNotFoundError:
        t0 = time.monotonic()
        return {
            "ran": body.cycles,
            "dry_run": body.dry_run,
            "results": [
                {"tick": i, "global": "S0_perceive", "agg": 0.67, "omni_mind": 0.62}
                for i in range(body.cycles)
            ],
            "duration_sec": round(time.monotonic() - t0, 3),
            "note": "stub — backend.oss.loop not on path",
        }


@router.get("/lab/inference")
async def lab_inference() -> dict[str, Any]:
    from oss.forge.lab_inference import lab_inference_status
    return lab_inference_status()


@router.get("/lab/saas-product/metrics")
async def lab_saas_metrics() -> dict[str, Any]:
    from oss.lab.saas_product import get_lab_metrics
    return get_lab_metrics()


@router.get("/lab/saas-product")
async def lab_saas_product(cycles: int = 3, use_adapter: bool = True) -> dict[str, Any]:
    from oss.lab.saas_product import run_oss_saas_lab
    try:
        return run_oss_saas_lab(cycles=cycles, use_adapter=use_adapter, dry_run=True)
    except Exception as exc:
        return {
            "stack": "oss_genomic_substrate",
            "cycles": cycles,
            "cycles_detail": [],
            "logs_written": 0,
            "dry_run": True,
            "error": str(exc),
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


# ---------------------------------------------------------------------------
# Binary Multiverse Engine routes
# ---------------------------------------------------------------------------

@router.get("/bme/status")
async def bme_status() -> dict[str, Any]:
    from backend.oss.core.bme_bridge import get_bme_bridge
    return get_bme_bridge().collect_stats().as_dict()


@router.get("/bme/flagships")
async def bme_flagships() -> dict[str, Any]:
    from backend.oss.core.bme_bridge import get_bme_bridge
    return get_bme_bridge().flagship_profiles()


@router.get("/bme/flagships/{species_name}")
async def bme_flagship(species_name: str) -> dict[str, Any]:
    from backend.oss.core.bme_bridge import get_bme_bridge
    return get_bme_bridge().flagship_profile(species_name)


@router.post("/bme/cycle")
async def bme_cycle(body: BMECycleRequest) -> dict[str, Any]:
    from backend.oss.core.bme_bridge import get_bme_bridge
    bridge = get_bme_bridge()
    last_result: dict[str, Any] = {}
    for _ in range(body.cycles):
        last_result = bridge.universe_pass(
            target_universe=body.target_universe,
            allow_migration=body.allow_migration and body.target_universe is None,
            allow_promotion=body.allow_promotion,
            allow_breakthrough=body.allow_breakthrough,
        )

    stats = bridge.collect_stats().as_dict()
    sovereign_pushed = False
    if body.push_sovereign_core:
        sovereign_pushed = await bridge.push_to_sovereign_core(
            universe_counts=last_result.get("universe_counts", {}),
            migrations=last_result.get("migrations", 0),
            promotions=last_result.get("promotions", 0),
            tick=last_result.get("agents_processed", 0),
        )

    return {
        "cycle_completed": True,
        "ran": body.cycles,
        "target_universe": body.target_universe,
        "allow_migration": body.allow_migration,
        "allow_promotion": body.allow_promotion,
        "allow_breakthrough": body.allow_breakthrough,
        "sovereign_core_pushed": sovereign_pushed,
        **last_result,
        **stats,
    }


# ── Civilization Kernel ───────────────────────────────────────────────────────

class KernelTickRequest(BaseModel):
    dry_run: bool = True
    ticks: int = Field(default=1, ge=1, le=10)


class KernelEvalRequest(BaseModel):
    role: str = Field(..., min_length=2, max_length=32)
    metrics: dict[str, Any] = Field(default_factory=dict)
    governor_approved: bool = False


@router.get("/kernel/status")
async def kernel_status_endpoint() -> dict[str, Any]:
    from oss.kernel.heartbeat import kernel_status
    return kernel_status()


@router.get("/kernel/territories")
async def kernel_territories() -> dict[str, Any]:
    from oss.kernel.data_territory import list_territories
    return {"territories": list_territories()}


@router.get("/kernel/agents")
async def kernel_agents(role: str = "") -> dict[str, Any]:
    from oss.kernel.agents import AGENT_REGISTRY, AgentRole, stage_spec, AgentStage
    if role:
        try:
            r = AgentRole(role.lower())
            spec = AGENT_REGISTRY[r]
            return {
                "role": r.value,
                "stages": [
                    {
                        "stage": s.stage.value,
                        "shards": [sh.value for sh in s.shards],
                    }
                    for s in spec.stages
                ],
            }
        except (ValueError, KeyError):
            raise HTTPException(400, f"Unknown role: {role}")
    return {
        "agents": [
            {"role": r.value, "stage_count": len(spec.stages)}
            for r, spec in AGENT_REGISTRY.items()
        ]
    }


@router.get("/kernel/shards")
async def kernel_shards(role: str = "", stage: str = "") -> dict[str, Any]:
    from oss.kernel.agents import AgentRole, AgentStage, shards_for_agent_stage
    from oss.kernel.shards import ROLE_PRIMARY_SHARDS
    if role and stage:
        try:
            r = AgentRole(role.lower())
            s = AgentStage(stage.lower())
            return {"role": r.value, "stage": s.value, "shards": shards_for_agent_stage(r, s)}
        except (ValueError, KeyError):
            raise HTTPException(400, f"Unknown role/stage: {role}/{stage}")
    return {
        "primary_shards": {k: [sh.value for sh in v] for k, v in ROLE_PRIMARY_SHARDS.items()}
    }


@router.post("/kernel/tick")
async def kernel_tick(body: KernelTickRequest) -> dict[str, Any]:
    from oss.kernel.heartbeat import tick
    results = []
    for _ in range(body.ticks):
        result = tick(dry_run=body.dry_run)
        results.append({
            "tick": result.tick,
            "blocked": result.blocked,
            "phases": [
                {"phase": p.phase.value, "metrics": p.metrics}
                for p in result.phases
            ],
        })
    return {"ticks": body.ticks, "dry_run": body.dry_run, "results": results, "all_ok": True}


@router.get("/kernel/fsm")
async def kernel_fsm() -> dict[str, Any]:
    from oss.kernel.state_machines import fsm_spec
    return fsm_spec()


@router.get("/kernel/orchestrator")
async def kernel_orchestrator_status() -> dict[str, Any]:
    from oss.kernel.orchestrator import orchestrator_status
    from oss.kernel.state_machines import CycleMachineState
    return orchestrator_status(CycleMachineState())


@router.post("/kernel/orchestrator/step")
async def kernel_orchestrator_step() -> dict[str, Any]:
    from oss.kernel.orchestrator import orchestrator_step
    from oss.kernel.state_machines import CycleMachineState
    from oss.kernel.sandbox import reset_sandbox
    reset_sandbox()
    st = CycleMachineState()
    return orchestrator_step(st, domain="growth", tick=1)


@router.get("/kernel/v1-plan")
async def kernel_v1_plan() -> dict[str, Any]:
    from oss.kernel.prompts import v1_implementation_plan
    return v1_implementation_plan()


@router.get("/kernel/sandbox")
async def kernel_sandbox() -> dict[str, Any]:
    from oss.kernel.sandbox import SandboxEnvironment, reset_sandbox
    from oss.kernel.rewards import compute_all_rewards
    reset_sandbox()
    env = SandboxEnvironment()
    metrics = env.run_cycle(domain="business", tick=1)
    rewards = compute_all_rewards(metrics)
    return {"metrics": metrics, "rewards": rewards}


@router.get("/kernel/training/schedule")
async def kernel_training_schedule() -> dict[str, Any]:
    from oss.kernel.training_schedule import schedule_overview
    return schedule_overview()


@router.get("/kernel/training/progress")
async def kernel_training_progress() -> dict[str, Any]:
    from oss.kernel.store import load_training_progress
    progress = load_training_progress()
    return {
        "global_phase": progress.global_phase.value,
        "roles": {
            r: {
                "global_phase": rp.global_phase.value,
                "metrics": rp.metrics,
                "governor_approved": rp.governor_approved,
            }
            for r, rp in progress.roles.items()
        },
    }


@router.get("/kernel/collaboration")
async def kernel_collaboration() -> dict[str, Any]:
    from oss.kernel.collaboration import collaboration_overview
    return collaboration_overview()


@router.post("/kernel/training/eval")
async def kernel_training_eval(body: KernelEvalRequest) -> dict[str, Any]:
    from oss.kernel.store import load_training_progress, save_training_progress
    from oss.kernel.training_schedule import record_eval
    progress = load_training_progress()
    result = record_eval(
        progress,
        role=body.role,
        metrics=body.metrics,
        governor_approved=body.governor_approved,
    )
    save_training_progress(progress)
    return result


# ---------------------------------------------------------------------------
# Substrate routes
# ---------------------------------------------------------------------------

@router.get("/substrate")
async def substrate_status() -> dict[str, Any]:
    from oss.substrate.genomic import get_genomic_substrate
    sub = get_genomic_substrate()
    return {"genomes": len(sub._genomes), "status": "ok"}


@router.get("/substrate/genome")
async def substrate_genome(
    role: str | None = None,
    domain: str | None = None,
    skill: str | None = None,
    capability: str | None = None,
    min_level: float = 0.0,
) -> dict[str, Any]:
    from oss.substrate.genomic import get_genomic_substrate
    sub = get_genomic_substrate()
    results: list[dict] = []
    if role:
        hits = sub.query_by_role(role)
        results = [h.to_dict() if hasattr(h, "to_dict") else h for h in hits]
    elif capability:
        from oss.substrate.genomic import query_genome
        segs = query_genome(capability=capability, domain=domain or "")
        results = segs
    elif domain or skill:
        traits: dict[str, float] = {}
        if domain:
            traits[domain] = min_level or 0.5
        if skill:
            traits[skill] = min_level or 0.5
        hits = sub.query_by_traits(traits)
        results = list(hits)
    else:
        results = []
    return {"results": results, "count": len(results)}


# ---------------------------------------------------------------------------
# Lab routes (trading)
# ---------------------------------------------------------------------------

@router.get("/lab/trading")
async def lab_trading(seed: int = 42) -> dict[str, Any]:
    from oss.lab.trading_strategy import trading_lab_comparison
    return trading_lab_comparison(seed=seed, dry_run=True)


# ---------------------------------------------------------------------------
# Ecosystem routes (note: /oss/ecosystem path keeps /oss segment so that
# when mounted with prefix /oss the full path is /oss/oss/ecosystem)
# ---------------------------------------------------------------------------

@router.get("/oss/ecosystem")
async def oss_ecosystem_status() -> dict[str, Any]:
    from oss.ecosystem.store import load_ecosystem_state
    from oss.ecosystem.orchestrator import ecosystem_status
    state = load_ecosystem_state()
    return ecosystem_status(state)


@router.get("/oss/ecosystem/fsm")
async def oss_ecosystem_fsm() -> dict[str, Any]:
    from oss.ecosystem.fsm import ecosystem_fsm_spec
    return ecosystem_fsm_spec()


@router.get("/oss/ecosystem/bootstrap")
async def oss_ecosystem_bootstrap() -> dict[str, Any]:
    from oss.ecosystem.bootstrap import oss_bootstrap_plan
    return oss_bootstrap_plan()


@router.post("/oss/ecosystem/step")
async def oss_ecosystem_step() -> dict[str, Any]:
    from oss.ecosystem.store import load_ecosystem_state, save_ecosystem_state
    from oss.ecosystem.orchestrator import ecosystem_step
    state = load_ecosystem_state()
    result = ecosystem_step(state, tick=1, domain="growth", dry_run=True)
    save_ecosystem_state(state)
    return result


# ---------------------------------------------------------------------------
# Architecture routes
# ---------------------------------------------------------------------------

@router.get("/architecture")
async def architecture_overview() -> dict[str, Any]:
    from oss.architecture.diagram import architecture_spec
    return architecture_spec()


@router.get("/architecture/modules")
async def architecture_modules() -> dict[str, Any]:
    from oss.architecture.modules import module_breakdown
    return module_breakdown()


# ---------------------------------------------------------------------------
# Living loop routes
# ---------------------------------------------------------------------------

@router.get("/living-loop")
async def living_loop_overview() -> dict[str, Any]:
    from oss.integration.living_loop import living_loop_status
    return living_loop_status()


@router.post("/living-loop/run")
async def living_loop_run() -> dict[str, Any]:
    from oss.integration.living_loop import run_living_cycle
    from oss.kernel.sandbox import reset_sandbox
    reset_sandbox()
    return run_living_cycle(domain="growth", tick=1, dry_run=True)


# ---------------------------------------------------------------------------
# Attention kernel lab routes
# ---------------------------------------------------------------------------

class AttentionRunRequest(BaseModel):
    # New-API fields (embed_dim, num_heads) and legacy (seq_len, d_model, n_heads)
    x: list[list[list[float]]] | list[list[float]] | None = Field(
        default=None, description="Input tensor as nested list [[...]] or [batch, seq, dim]"
    )
    seq_len: int = Field(default=8, ge=1, le=512)
    d_model: int | None = Field(default=None, ge=8, le=2048)
    n_heads: int | None = Field(default=None, ge=1, le=32)
    embed_dim: int = Field(default=64, ge=8, le=2048)
    num_heads: int = Field(default=4, ge=1, le=32)
    training_binary_ratio: float = Field(default=1.0, ge=0.0, le=2.0)
    temperature: float = Field(default=1.0, gt=0.0, le=10.0)
    max_growth: float = Field(default=0.5, ge=0.0, le=10.0)
    seed: int = Field(default=42, ge=0)
    agent_id: str = Field(default="lab_runner", max_length=64)
    use_torch: bool = Field(default=False, description="Use Triton GPU kernel if available")


@router.get("/lab/attention")
async def lab_attention_status() -> dict[str, Any]:
    """MA-INBL attention kernel status and backend availability."""
    from oss.attention.kernel import TRITON_AVAILABLE
    from oss.attention.telemetry import AttentionTelemetrySink
    sink = AttentionTelemetrySink()
    return {
        "status": "ok",
        "backend": "triton" if TRITON_AVAILABLE else "numpy",
        "triton_available": TRITON_AVAILABLE,
        "total_logged_entries": len(sink.load_all()),
        "components": ["MA-INBL", "BinaryLinear-XNOR+popcount",
                       "dual-scale", "MGC", "ORS"],
    }


@router.get("/lab/attention/ping")
async def lab_attention_ping() -> dict[str, Any]:
    """Health check for the MA-INBL attention sub-system."""
    return {"status": "ok", "component": "attention"}


@router.get("/lab/attention/telemetry")
async def lab_attention_telemetry(limit: int = 100) -> dict[str, Any]:
    """Return the most recent attention telemetry entries."""
    from oss.lab.metrics import load_logs
    from oss.attention.telemetry import AttentionTelemetrySink
    # Entries from the attention-specific log
    sink = AttentionTelemetrySink()
    attn_entries = sink.load_all()
    # Also expose OSS lab entries that originated from attention
    oss_entries = [
        e for e in load_logs()
        if e.get("role") == "attention_kernel"
    ]
    all_entries = attn_entries[-limit:]
    return {
        "total_attention_log": len(attn_entries),
        "total_oss_lab": len(oss_entries),
        "entries": all_entries,
    }


@router.post("/lab/attention/run")
async def lab_attention_run(body: AttentionRunRequest) -> dict[str, Any]:
    """Run a MA-INBL attention pass and record telemetry."""
    import numpy as np
    from oss.attention.attention import MA_INBLAttention
    from oss.attention.telemetry import AttentionTelemetrySink

    # Resolve dimensions (new API takes precedence over legacy)
    eff_dim = body.d_model or body.embed_dim
    eff_heads = body.n_heads or body.num_heads

    if eff_dim % eff_heads != 0:
        raise HTTPException(
            400, f"embed_dim={eff_dim} must be divisible by num_heads={eff_heads}"
        )

    if body.x is not None:
        x = np.array(body.x, dtype=np.float32)
    else:
        rng = np.random.default_rng(body.seed)
        x = rng.standard_normal((body.seq_len, eff_dim)).astype(np.float32)

    from oss.attention.kernel import TRITON_AVAILABLE
    backend = "triton" if (body.use_torch and TRITON_AVAILABLE) else ("triton" if body.use_torch else "numpy")
    attn = MA_INBLAttention(
        embed_dim=eff_dim,
        num_heads=eff_heads,
        training_binary_ratio=body.training_binary_ratio,
        temperature=body.temperature,
        max_growth=body.max_growth,
        seed=body.seed,
        backend=backend,
    )
    output, tel = attn.forward(x)

    sink = AttentionTelemetrySink()
    record = sink.record(tel, agent_id=body.agent_id)

    return {
        "output_shape": list(output.shape),
        "output_norm": float(np.linalg.norm(output)),
        "telemetry": tel,
        "logged": record,
        "backend": attn.active_backend,
        "use_torch": body.use_torch,
        "triton_available": TRITON_AVAILABLE,
    }
