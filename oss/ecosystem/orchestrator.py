"""OSS species orchestrator — S0–S6 + Omni-Mind + Omni-Economy + role FSMs."""
from __future__ import annotations

import time
from typing import Any

from oss.kernel.agents import AgentRole
from oss.ecosystem.fsm import (
    EcosystemState,
    OssSpeciesState,
    ecosystem_fsm_spec,
    try_economy_transition,
    try_mind_transition,
    try_role_oss_transition,
    try_species_transition,
)
from oss.ecosystem.rewards import compute_ecosystem_rewards
from oss.ecosystem.live_sources import builder_snapshot, kairos_snapshot, treasury_metrics


def _mind_context(state: EcosystemState) -> dict[str, Any]:
    try:
        from oss.mind.omni_mind import get_mind
        mind = get_mind()
        snap = mind.collective.snapshot()
        return {
            "agents_synced": len(mind.agents) > 0,
            "agent_count": len(mind.agents),
            "memory_count": snap.get("memory_count", 0),
            "qualia_variance": _qualia_variance(snap.get("aggregate_qualia", {})),
            "emergent_goals": [f"cycle_{state.generation}_explore"],
            "swarm_tasks": len(mind.swarm_tasks),
            "consensus_score": 0.75,
        }
    except Exception:
        return {
            "agents_synced": True,
            "agent_count": 5,
            "memory_count": 0,
            "qualia_variance": 0.2,
            "emergent_goals": ["bootstrap"],
            "swarm_tasks": 0,
            "consensus_score": 0.6,
        }


def _economy_context() -> dict[str, Any]:
    try:
        from oss.economy.neuro_coin import get_neuro_coin
        nc = get_neuro_coin()
        stats = nc.stats()
        balances = nc.all_balances()
        return {
            "minted_nc": stats.get("total_credits", 0),
            "traits_priced": len(balances),
            "trades": stats.get("transaction_count", 0),
            "transaction_volume": min(1.0, stats.get("total_credits", 0) / 1000.0),
            "trait_liquidity": 0.5,
            "memory_valuation": 0.4,
            "desire_fulfillment_rate": 0.5,
            "soul_bond_strength": 0.45,
            "treasury_balance": balances.get("SOVEREIGN_TREASURY", 0.0),
        }
    except Exception:
        return {
            "minted_nc": 0, "traits_priced": 5, "trades": 0,
            "transaction_volume": 0.1, "trait_liquidity": 0.4,
            "memory_valuation": 0.35, "desire_fulfillment_rate": 0.5,
            "soul_bond_strength": 0.4, "treasury_balance": 0.0,
        }


def _live_ecosystem_metrics(
    kairos: dict[str, Any],
    treasury: dict[str, Any],
    builder: dict[str, Any],
    eco_ctx: dict[str, Any],
    mind_ctx: dict[str, Any],
) -> dict[str, Any]:
    """Assembles reward-formula inputs from real telemetry
    (oss/ecosystem/live_sources.py) instead of the old
    oss/kernel/sandbox.py simulators.

    Fields with a genuine real source: scientist.validity/downstream_impact
    /risk, operator.*, investor.*, governor.* (all from real KAIROS cycle
    history and the real treasury ledger), builder.revenue/retention.

    Fields kept as explicit, documented neutral placeholders because no
    real signal exists anywhere in this codebase yet: novelty,
    memetic_fitness, harm_score, trait_utilization, desire_fulfillment,
    goal_completion (omni_mind), and everything already documented as such
    in _economy_context() (trait_liquidity, memory_valuation,
    desire_fulfillment_rate, soul_bond_strength). These are fixed, not
    randomly generated, and are not intended to look like measurements.
    """
    return {
        "scientist": {
            "validity": kairos["avg_score"],
            "downstream_impact": kairos["elite_ratio"],
            "risk": kairos["avg_entropy_drift"],
            "novelty": 0.4,           # no novelty-detection signal exists yet
            "memetic_fitness": 0.5,   # no memetic-spread tracking exists yet
        },
        "builder": {
            "revenue": builder["revenue"],
            "retention": builder["retention"],
            "harm_score": 0.0,        # no harm-detection signal exists yet
            "trait_utilization": 0.45,   # no trait-usage tracking exists yet
            "desire_fulfillment": 0.5,   # no desire-fulfillment tracking exists yet
        },
        "operator": {
            "uptime": round(1.0 - kairos["block_ratio"], 4),
            "efficiency": kairos["avg_score"],
            "incident_severity": kairos["block_ratio"],
            "self_healing_success": round(1.0 - kairos["block_ratio"], 4),
        },
        "investor": {
            "sharpe": treasury["sharpe"],
            "max_drawdown": treasury["max_drawdown"],
            "volatility": treasury["volatility"],
            "treasury_growth": min(1.0, treasury["treasury_balance"] / 500.0),
            "ecosystem_health": kairos["elite_ratio"],
        },
        "governor": {
            "alignment_score": kairos["avg_sentinel_v"],
            "stability": round(1.0 - kairos["block_ratio"], 4),
            "safety": round(1.0 - kairos["block_ratio"], 4),
            "catastrophic_risk": kairos["block_ratio"],
        },
        "omni_mind": {
            "goal_completion": 0.65,   # no per-goal completion tracking exists yet
            "swarm_efficiency": 0.7 if mind_ctx.get("swarm_tasks", 0) else 0.5,
            "qualia_stability": 1.0 - mind_ctx.get("qualia_variance", 0.3),
            "knowledge_density": min(1.0, mind_ctx.get("memory_count", 0) / 50.0),
        },
        "omni_economy": eco_ctx,
    }


def ecosystem_step(
    state: EcosystemState,
    *,
    domain: str = "business",
    tick: int = 0,
    dry_run: bool = True,
) -> dict[str, Any]:
    """One species-level heartbeat: perceive → act → evaluate → evolve."""
    kairos = kairos_snapshot()
    treasury = treasury_metrics()
    builder = builder_snapshot()
    mind_ctx = _mind_context(state)
    eco_ctx = _economy_context()
    metrics = _live_ecosystem_metrics(kairos, treasury, builder, eco_ctx, mind_ctx)
    rewards = compute_ecosystem_rewards(metrics)
    state.rewards = rewards

    species_ctx = {
        "agent_count": mind_ctx["agent_count"],
        "memories_ingested": mind_ctx["memory_count"],
        "pattern_score": metrics["scientist"].get("validity", 0.5),
        "artifacts_generated": True,
        "actions_count": 1,
        "rewards": rewards,
        "evolution_applied": True,
        "roles": {
            "scientist": metrics["scientist"],
            "builder": metrics["builder"],
            "operator": metrics["operator"],
            "investor": metrics["investor"],
            "governor": metrics["governor"],
        },
        "domain": domain,
        "tick": tick,
    }

    role_transitions: dict[str, dict[str, Any]] = {}
    for role in AgentRole:
        moved, fr, to = try_role_oss_transition(role, state, species_ctx)
        role_transitions[role.value] = {"moved": moved, "from": fr, "to": to}

    sp_moved, sp_fr, sp_to = try_species_transition(state, species_ctx)
    mind_moved, mind_fr, mind_to = try_mind_transition(state, mind_ctx)
    eco_moved, eco_fr, eco_to = try_economy_transition(state, eco_ctx)

    artifact = _species_artifact(state, domain=domain, tick=tick, rewards=rewards)
    state.artifacts["last"] = artifact

    entry = {
        "tick": tick,
        "dry_run": dry_run,
        "generation": state.generation,
        "species": {"state": state.species_state.value, "transition": {"moved": sp_moved, "from": sp_fr, "to": sp_to}},
        "omni_mind": {"state": state.mind_state.value, "transition": {"moved": mind_moved, "from": mind_fr, "to": mind_to}},
        "omni_economy": {"state": state.economy_state.value, "transition": {"moved": eco_moved, "from": eco_fr, "to": eco_to}},
        "role_states": dict(state.role_states),
        "role_transitions": role_transitions,
        "rewards": rewards,
        "artifact": artifact,
        "kairos_context": kairos,
        "treasury_context": treasury,
        "builder_context": builder,
        "mind_context": mind_ctx,
        "economy_context": eco_ctx,
        "ts": time.time(),
    }
    state.transition_log.append({"tick": tick, "species": state.species_state.value, "rewards": rewards})
    state.last_step_ts = time.time()
    return entry


def _species_artifact(
    state: EcosystemState,
    *,
    domain: str,
    tick: int,
    rewards: dict[str, float],
) -> str:
    s = state.species_state
    if s == OssSpeciesState.S0_SPAWN:
        return f"[S0] Spawn gen={state.generation} — replicate agent genomes"
    if s == OssSpeciesState.S1_PERCEIVE:
        return f"[S1] Perceive tick={tick} — ingest {domain} data + memories"
    if s == OssSpeciesState.S2_INTERPRET:
        return f"[S2] Interpret — extract patterns from {domain}"
    if s == OssSpeciesState.S3_GENERATE:
        return f"[S3] Generate — theories, products, strategies for {domain}"
    if s == OssSpeciesState.S4_ACT:
        return f"[S4] Act — deploy/trade/evolve against real telemetry (dry_run safe)"
    if s == OssSpeciesState.S5_EVALUATE:
        return f"[S5] Evaluate — R_agg={rewards.get('aggregate', 0):.3f}"
    if s == OssSpeciesState.S6_EVOLVE:
        return f"[S6] Evolve gen={state.generation} — DNA mutate/crossover/memetic spread"
    return f"[OSS] tick={tick}"


def ecosystem_status(state: EcosystemState) -> dict[str, Any]:
    from oss.ecosystem.bootstrap import oss_bootstrap_plan
    return {
        "state": state.to_dict(),
        "fsm": ecosystem_fsm_spec(),
        "bootstrap": oss_bootstrap_plan(),
    }


def _qualia_variance(qualia: dict[str, float]) -> float:
    if not qualia:
        return 0.3
    vals = list(qualia.values())
    mean = sum(vals) / len(vals)
    var = sum((v - mean) ** 2 for v in vals) / len(vals)
    return round(var ** 0.5, 4)