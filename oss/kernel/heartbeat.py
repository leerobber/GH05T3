"""Civilization Kernel heartbeat — self-sustaining intelligence economy loop."""
from __future__ import annotations

import logging
import time
from typing import Any

from oss.kernel.agents import agent_for_phase, list_agents, role_overview_table, training_targets_for_tick
from oss.kernel.collaboration import ingest_tick_feedback, run_collaboration_loop
from oss.kernel.data_territory import territory_for_tick
from oss.kernel.shards import list_shards
from oss.kernel.training_schedule import progress_report, schedule_overview
from oss.kernel.orchestrator import orchestrator_step, orchestrator_status
from oss.kernel.store import append_cycle_log, load_cycle_state, load_training_progress, save_cycle_state
from oss.kernel.finance import estimate_tick_revenue, economy_snapshot, investment_scan
from oss.kernel.governance import authorize_action, evaluate_tick_budget, preflight
from oss.kernel.schemas import HeartbeatPhase, KernelState, PhaseResult, Pillar, TickResult
from oss.kernel.science import next_research_domain, run_research_phase
from oss.kernel.execution import run_improvement_phase
from oss.kernel.store import append_tick_log, load_state, save_state
from oss.kernel.treasury import allocate_inflow, ensure_treasury_seeded, treasury_balance

LOG = logging.getLogger("oss.kernel.heartbeat")


def kernel_status() -> dict[str, Any]:
    state = load_state()
    gov = preflight()
    terr = territory_for_tick(state.tick + 1)
    cycle_st = load_cycle_state()
    from oss.ecosystem.orchestrator import ecosystem_status
    from oss.ecosystem.store import load_ecosystem_state
    eco_st = load_ecosystem_state()
    return {
        "name": "Self-Sustaining Autonomous Intelligence State",
        "version": "0.2.0",
        "pillars": [p.value for p in Pillar],
        "agents": role_overview_table(),
        "agent_count": len(list_agents()),
        "shard_count": len(list_shards()),
        "state": state.to_dict(),
        "treasury_nc": treasury_balance(),
        "governance": gov,
        "next_territory": terr.to_dict(),
        "training_targets": training_targets_for_tick(domain=state.last_domain, tick=state.tick + 1),
        "training_schedule": schedule_overview(),
        "training_progress": progress_report(load_training_progress()),
        "economy": economy_snapshot(),
        "loop": [
            "research → monetize → treasury → invest → fund → improve → govern",
        ],
        "collaboration_loop": (
            "scientist → builder → operator → investor → governor → training feedback"
        ),
        "cycle_fsm": orchestrator_status(cycle_st),
        "oss_ecosystem": ecosystem_status(eco_st),
    }


def tick(*, dry_run: bool = True) -> TickResult:
    """
    One civilization heartbeat.

    1. Research (theory engine)
    2. Monetize (finance engine)
    3. Treasury + invest + fund + improve (finance + ops)
    4. Govern (constitution engine)
    """
    state = load_state()
    state.tick += 1
    tick_n = state.tick
    phases: list[PhaseResult] = []

    allowed, reason = authorize_action("autonomous_tick", context={})
    if not allowed:
        result = TickResult(tick=tick_n, dry_run=dry_run, phases=[], blocked=True, block_reason=reason)
        append_tick_log(result)
        return result

    territory = territory_for_tick(tick_n)
    domain = next_research_domain(state.last_domain)
    state.last_domain = domain

    # ── 1. RESEARCH ──────────────────────────────────────────────────────
    research = run_research_phase(
        domain=domain, territory_key=territory.key, dry_run=dry_run,
    )
    if not dry_run:
        state.cumulative_research_runs += 1
    phases.append(PhaseResult(
        phase=HeartbeatPhase.RESEARCH,
        pillar=Pillar.SCIENCE,
        ok="error" not in research,
        summary=f"[{agent_for_phase(HeartbeatPhase.RESEARCH).value}] {territory.key} → {domain}",
        metrics={**research, "agent": agent_for_phase(HeartbeatPhase.RESEARCH).value},
    ))

    # ── 2. MONETIZE ──────────────────────────────────────────────────────
    revenue = estimate_tick_revenue(tick=tick_n, dry_run=dry_run)
    monetize_ok, monetize_reason = authorize_action("accrue_simulated_revenue")
    phases.append(PhaseResult(
        phase=HeartbeatPhase.MONETIZE,
        pillar=Pillar.FINANCE,
        ok=monetize_ok,
        summary=f"Revenue accrual {revenue:.2f} NC ({monetize_reason})",
        metrics={"revenue_nc": revenue, "streams": list(__import__(
            "oss.kernel.finance", fromlist=["REVENUE_STREAMS"]
        ).REVENUE_STREAMS)},
    ))

    # ── 3. TREASURY ──────────────────────────────────────────────────────
    if not dry_run:
        ensure_treasury_seeded()
    if not dry_run and revenue > 0:
        try:
            from oss.economy.neuro_coin import get_neuro_coin
            get_neuro_coin().earn("SOVEREIGN_TREASURY", revenue, f"kernel tick {tick_n} revenue")
            state.cumulative_revenue += revenue
        except Exception as exc:
            LOG.warning("treasury credit failed: %s", exc)

    bal = treasury_balance()
    allocation = allocate_inflow(revenue if not dry_run else revenue or 10.0, dry_run=dry_run)
    phases.append(PhaseResult(
        phase=HeartbeatPhase.TREASURY,
        pillar=Pillar.FINANCE,
        ok=True,
        summary=f"Treasury {bal:.2f} NC — allocated inflow",
        metrics={"balance": bal, "allocation": allocation},
    ))

    # ── 4. INVEST ────────────────────────────────────────────────────────
    invest = investment_scan(treasury_balance=bal)
    research_budget = allocation.get("buckets", {}).get("research", 0.0)
    if dry_run:
        spend_ok, spend_reason = True, "dry-run — budget check skipped"
    else:
        spend_ok, spend_reason = evaluate_tick_budget(
            proposed_spend=research_budget, treasury_balance=max(bal, 1.0),
        )
    phases.append(PhaseResult(
        phase=HeartbeatPhase.INVEST,
        pillar=Pillar.FINANCE,
        ok=spend_ok,
        summary=spend_reason,
        metrics=invest,
    ))

    if not spend_ok and not dry_run:
        result = TickResult(
            tick=tick_n, dry_run=dry_run, phases=phases,
            treasury_balance=bal, blocked=True, block_reason=spend_reason,
        )
        save_state(state)
        append_tick_log(result)
        return result

    # ── 5. FUND + IMPROVE ────────────────────────────────────────────────
    improve = run_improvement_phase(
        research_domain=domain,
        fund_research_nc=research_budget,
        dry_run=dry_run,
    )
    phases.append(PhaseResult(
        phase=HeartbeatPhase.FUND,
        pillar=Pillar.EXECUTION,
        ok=True,
        summary=f"Funded agents for {domain}",
        metrics={"budget_nc": research_budget},
    ))
    collab = run_collaboration_loop(
        tick=tick_n,
        domain=domain,
        territory=territory.key,
        revenue_nc=revenue,
        dry_run=dry_run,
    )
    feedback = ingest_tick_feedback(collab, revenue_nc=revenue)
    cycle_st = load_cycle_state()
    orch = orchestrator_step(
        cycle_st, domain=domain, tick=tick_n, dry_run=dry_run,
    )
    save_cycle_state(cycle_st)
    append_cycle_log(orch)
    from oss.ecosystem.orchestrator import ecosystem_step
    from oss.ecosystem.store import (
        append_ecosystem_log, load_ecosystem_state, save_ecosystem_state,
    )
    eco_st = load_ecosystem_state()
    eco = ecosystem_step(eco_st, domain=domain, tick=tick_n, dry_run=dry_run)
    save_ecosystem_state(eco_st)
    append_ecosystem_log(eco)
    from oss.integration.living_loop import run_living_cycle
    living = run_living_cycle(domain=domain, tick=tick_n, dry_run=dry_run)
    phases.append(PhaseResult(
        phase=HeartbeatPhase.IMPROVE,
        pillar=Pillar.EXECUTION,
        ok=True,
        summary=(
            f"FSM {orch['global_state']} — {orch['active_agent']} "
            f"R={orch['rewards'].get('aggregate', 0):.3f}"
        ),
        metrics={
            **improve,
            "collaboration": collab,
            "training_feedback": feedback,
            "orchestrator": orch,
            "oss_ecosystem": eco,
            "living_loop": living,
        },
    ))

    # ── 6. GOVERN ────────────────────────────────────────────────────────
    gov = preflight()
    phases.append(PhaseResult(
        phase=HeartbeatPhase.GOVERN,
        pillar=Pillar.GOVERNANCE,
        ok=gov.get("training_ready", False) or dry_run,
        summary=f"[{agent_for_phase(HeartbeatPhase.GOVERN).value}] constitution + guardrails",
        metrics={**gov, "agent": agent_for_phase(HeartbeatPhase.GOVERN).value},
    ))

    state.last_tick_ts = time.time()
    save_state(state)
    result = TickResult(tick=tick_n, dry_run=dry_run, phases=phases, treasury_balance=bal)
    append_tick_log(result)
    LOG.info("Kernel tick %d complete (dry_run=%s)", tick_n, dry_run)
    return result