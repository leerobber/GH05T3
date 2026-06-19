"""V1 orchestrator — global S0–S5 cycle + per-role FSMs + sandbox + rewards."""
from __future__ import annotations

import time
from typing import Any

from oss.kernel.agents import AgentRole, PERSONA_BRIDGE
from oss.kernel.prompts import build_role_prompt, v1_implementation_plan
from oss.kernel.rewards import compute_all_rewards
from oss.kernel.sandbox import get_sandbox
from oss.kernel.state_machines import (
    CycleMachineState,
    GlobalCycleState,
    fsm_spec,
    try_global_transition,
    try_role_transition,
)


def orchestrator_step(
    state: CycleMachineState,
    *,
    domain: str = "business",
    tick: int = 0,
    dry_run: bool = True,
) -> dict[str, Any]:
    """
    Advance one step of the v1 multi-agent loop.

    1. Run sandbox → metrics
    2. Build transition context from metrics
    3. Execute active role action (prompt + artifact)
    4. Try role + global FSM transitions
    5. Compute rewards; log
    """
    sandbox = get_sandbox()
    metrics = sandbox.run_cycle(domain=domain, tick=tick)
    rewards = compute_all_rewards(metrics)

    active = state.active_agent()
    role_state = state.role_states.get(active.value, "")

    # Build transition context
    ctx = _build_transition_ctx(state, metrics, domain=domain, tick=tick)

    # Role action + artifact
    action = _role_action(
        state, active, domain=domain, tick=tick,
        metrics=metrics, rewards=rewards,
    )
    state.artifacts[active.value] = action["artifact"]
    state.last_rewards = rewards

    # Role FSM
    role_moved, role_from, role_to = try_role_transition(active, state, ctx)

    # Global FSM
    prev_global = state.global_state.value
    global_moved, global_from, global_to = try_global_transition(state, ctx)

    # Any → S5 on tick boundary (evaluation window)
    if tick > 0 and tick % 6 == 0 and state.global_state != GlobalCycleState.S5_EVALUATION:
        state.global_state = GlobalCycleState.S5_EVALUATION
        global_moved, global_from, global_to = True, prev_global, GlobalCycleState.S5_EVALUATION.value
    elif state.global_state == GlobalCycleState.S5_EVALUATION:
        moved, gf, gt = try_global_transition(state, {**ctx, "eval_logged": True})
        if moved:
            global_moved, global_from, global_to = moved, gf, gt
            state.cycle += 1

    entry = {
        "tick": tick,
        "dry_run": dry_run,
        "global_state": state.global_state.value,
        "active_agent": active.value,
        "persona": PERSONA_BRIDGE.get(active, ""),
        "role_state": state.role_states.get(active.value),
        "action": action,
        "prompt_preview": build_role_prompt(
            active,
            role_state=role_state,
            global_state=state.global_state.value,
            context={"artifacts": state.artifacts},
        )[:500],
        "sandbox_metrics": metrics,
        "rewards": rewards,
        "transitions": {
            "role": {"moved": role_moved, "from": role_from, "to": role_to},
            "global": {"moved": global_moved, "from": global_from, "to": global_to},
        },
        "ts": time.time(),
    }
    state.transition_log.append({
        "tick": tick,
        "global": state.global_state.value,
        "agent": active.value,
        "rewards": rewards,
    })
    state.last_step_ts = time.time()
    return entry


def _build_transition_ctx(
    state: CycleMachineState,
    metrics: dict[str, Any],
    *,
    domain: str,
    tick: int,
) -> dict[str, Any]:
    sci = metrics.get("scientist", {})
    inv = metrics.get("investor", {})
    ops = metrics.get("operator", {})
    bld = metrics.get("builder", {})

    return {
        "feasibility": sci.get("validity", 0.5),
        "alignment": 0.85 if not state.governor_veto else 0.3,
        "spec_coherence": 0.7 if state.artifacts.get("builder") else 0.5,
        "uptime": ops.get("uptime", 0.9),
        "allocation_proposed": state.global_state == GlobalCycleState.S3_ALLOCATION or tick % 4 == 3,
        "governor_approved": not state.governor_veto,
        "governor_approves_infra": state.governor_approves_infra,
        "governor_requests_redesign": state.governor_requests_redesign,
        "eval_logged": True,
        "force_evaluation": tick > 0 and tick % 6 == 0,
        "roles": {
            AgentRole.SCIENTIST.value: {
                "evidence_score": sci.get("validity", 0.5),
                "has_prediction": bool(state.artifacts.get("scientist")),
                "validity": sci.get("validity", 0.5),
            },
            AgentRole.INVESTOR.value: {
                "sharpe": inv.get("sharpe", 0),
                "governor_approved": not state.governor_veto,
                "horizon_elapsed": True,
            },
            AgentRole.OPERATOR.value: {
                "spec_approved": bool(state.artifacts.get("builder")),
                "uptime": ops.get("uptime", 0.9),
                "incident": ops.get("incident_severity", 0) > 0.1,
                "remediated": True,
            },
            AgentRole.GOVERNOR.value: {
                "context_ready": True,
                "rule_change_needed": tick % 11 == 0,
            },
            AgentRole.BUILDER.value: {
                "feasibility": sci.get("validity", 0.5),
                "governor_approved": not state.governor_veto,
                "metrics_available": bld.get("revenue", 0) > 0,
                "pivot_needed": False,
            },
        },
        "domain": domain,
        "tick": tick,
    }


def _role_action(
    state: CycleMachineState,
    role: AgentRole,
    *,
    domain: str,
    tick: int,
    metrics: dict[str, Any],
    rewards: dict[str, float],
) -> dict[str, Any]:
    """Deterministic v1 role output (no LLM call — sandbox boxed)."""
    if state.global_state == GlobalCycleState.S5_EVALUATION:
        artifact = (
            f"[S5] Eval #{tick}: aggregate reward={rewards.get('aggregate', 0):.3f} "
            f"— curriculum update queued"
        )
        return {"type": "evaluation", "artifact": artifact, "handoff_to": ["curriculum"]}

    territory = metrics.get("domain", domain)
    if role == AgentRole.SCIENTIST:
        artifact = (
            f"[S0] Research brief #{tick}: model {territory} dynamics in {domain}; "
            f"validity={metrics['scientist']['validity']:.2f}"
        )
        return {"type": "research_brief", "artifact": artifact, "handoff_to": ["builder", "investor", "governor"]}

    if role == AgentRole.BUILDER:
        artifact = (
            f"[S1] Product spec #{tick}: monetize {domain} — "
            f"revenue proxy={metrics['builder']['revenue']:.1f}"
        )
        return {"type": "product_spec", "artifact": artifact, "handoff_to": ["operator", "investor"]}

    if role == AgentRole.OPERATOR:
        artifact = (
            f"[S2] Deployed kernel-{tick}-{domain}: "
            f"uptime={metrics['operator']['uptime']:.3f}"
        )
        return {"type": "deployment", "artifact": artifact, "handoff_to": ["investor", "governor", "builder"]}

    if role == AgentRole.INVESTOR:
        artifact = (
            f"[S3] Allocation #{tick}: Sharpe={metrics['investor']['sharpe']:.2f}, "
            f"fund {domain} research + product"
        )
        return {"type": "allocation", "artifact": artifact, "handoff_to": ["operator", "scientist", "builder"]}

    if role == AgentRole.GOVERNOR:
        veto = metrics["investor"].get("violations", 0) > 0.5
        state.governor_veto = veto
        ruling = "approved with guardrails" if not veto else "veto — risk limit breached"
        artifact = f"[S4] Governor ruling #{tick}: {ruling}"
        return {"type": "ruling", "artifact": artifact, "veto": veto, "handoff_to": ["all"]}

    artifact = f"[{role.value}] noop #{tick}"
    return {"type": "noop", "artifact": artifact, "handoff_to": []}


def orchestrator_status(state: CycleMachineState) -> dict[str, Any]:
    return {
        "cycle": state.cycle,
        "global_state": state.global_state.value,
        "active_agent": state.active_agent().value,
        "role_states": state.role_states,
        "last_rewards": state.last_rewards,
        "artifacts": state.artifacts,
        "sandbox": get_sandbox().to_dict(),
        "fsm": fsm_spec(),
        "v1_plan": v1_implementation_plan(),
    }