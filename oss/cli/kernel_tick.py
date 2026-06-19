#!/usr/bin/env python3
"""Run one Civilization Kernel heartbeat tick."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from oss.kernel.agents import list_agents, role_overview_table
from oss.kernel.collaboration import collaboration_overview
from oss.kernel.heartbeat import kernel_status, tick
from oss.kernel.data_territory import list_territories
from oss.kernel.shards import list_shards
from oss.kernel.orchestrator import orchestrator_status, orchestrator_step
from oss.kernel.prompts import v1_implementation_plan
from oss.kernel.state_machines import fsm_spec
from oss.kernel.store import append_cycle_log, load_cycle_state, load_state, load_training_progress, save_cycle_state
from oss.kernel.training_schedule import progress_report, schedule_overview
from oss.ecosystem.bootstrap import oss_bootstrap_plan
from oss.ecosystem.fsm import ecosystem_fsm_spec
from oss.ecosystem.orchestrator import ecosystem_status, ecosystem_step
from oss.architecture.diagram import architecture_spec
from oss.integration.living_loop import living_loop_status, run_living_cycle
from oss.ecosystem.store import append_ecosystem_log, load_ecosystem_state, save_ecosystem_state


def main() -> int:
    ap = argparse.ArgumentParser(description="Civilization Kernel heartbeat")
    ap.add_argument("--status", action="store_true", help="Print kernel status")
    ap.add_argument("--territories", action="store_true", help="List data territories")
    ap.add_argument("--agents", action="store_true", help="List five civilization agents + stages")
    ap.add_argument("--shards", action="store_true", help="List data shard catalog")
    ap.add_argument("--schedule", action="store_true", help="Training schedule phases 0–3 + unlock gates")
    ap.add_argument("--progress", action="store_true", help="Per-role training unlock progress")
    ap.add_argument("--collaboration", action="store_true", help="Six-step multi-agent loop spec")
    ap.add_argument("--fsm", action="store_true", help="Global + role state machine spec")
    ap.add_argument("--orchestrator", action="store_true", help="Current FSM cycle state + rewards")
    ap.add_argument("--v1-plan", action="store_true", help="Minimal v1 implementation plan")
    ap.add_argument("--step", action="store_true", help="Advance one orchestrator FSM step")
    ap.add_argument("--ecosystem", action="store_true", help="OSS species FSM status (S0–S6)")
    ap.add_argument("--oss-fsm", action="store_true", help="Full OSS ecosystem FSM spec")
    ap.add_argument("--oss-bootstrap", action="store_true", help="OSS bootstrap plan phases 1–5")
    ap.add_argument("--eco-step", action="store_true", help="Advance one OSS species FSM step")
    ap.add_argument("--architecture", action="store_true", help="OSS architecture diagram + hooks")
    ap.add_argument("--living-loop", action="store_true", help="Run or show DNA→Mind→Economy loop")
    ap.add_argument("--lab-trading", action="store_true", help="Run trading strategy lab (old vs OSS stack)")
    ap.add_argument("--lab-saas", action="store_true", help="Run SaaS product design lab (old vs OSS stack)")
    ap.add_argument("--lab-cycles", type=int, default=10, help="OSS lab evolution cycles")
    ap.add_argument("--live", action="store_true", help="Execute live NC movements (default: dry-run)")
    ap.add_argument("--ticks", type=int, default=1, help="Number of ticks to run")
    args = ap.parse_args()

    if args.territories:
        print(json.dumps({"territories": list_territories()}, indent=2))
        return 0

    if args.agents:
        print(json.dumps({"overview": role_overview_table(), "agents": list_agents()}, indent=2))
        return 0

    if args.shards:
        print(json.dumps({"shards": list_shards()}, indent=2))
        return 0

    if args.schedule:
        print(json.dumps(schedule_overview(), indent=2))
        return 0

    if args.progress:
        print(json.dumps(progress_report(load_training_progress()), indent=2))
        return 0

    if args.collaboration:
        print(json.dumps(collaboration_overview(), indent=2))
        return 0

    if args.fsm:
        print(json.dumps(fsm_spec(), indent=2))
        return 0

    if args.orchestrator:
        print(json.dumps(orchestrator_status(load_cycle_state()), indent=2))
        return 0

    if args.v1_plan:
        print(json.dumps(v1_implementation_plan(), indent=2))
        return 0

    if args.step:
        cycle_st = load_cycle_state()
        kstate = load_state()
        result = orchestrator_step(
            cycle_st, domain=kstate.last_domain, tick=kstate.tick + 1, dry_run=not args.live,
        )
        save_cycle_state(cycle_st)
        append_cycle_log(result)
        print(json.dumps(result, indent=2))
        return 0

    if args.ecosystem:
        print(json.dumps(ecosystem_status(load_ecosystem_state()), indent=2))
        return 0

    if args.oss_fsm:
        print(json.dumps(ecosystem_fsm_spec(), indent=2))
        return 0

    if args.oss_bootstrap:
        print(json.dumps(oss_bootstrap_plan(), indent=2))
        return 0

    if args.eco_step:
        eco = load_ecosystem_state()
        kstate = load_state()
        result = ecosystem_step(
            eco, domain=kstate.last_domain, tick=kstate.tick + 1, dry_run=not args.live,
        )
        save_ecosystem_state(eco)
        append_ecosystem_log(result)
        print(json.dumps(result, indent=2))
        return 0

    if args.architecture:
        print(json.dumps(architecture_spec(), indent=2))
        return 0

    if args.living_loop:
        kstate = load_state()
        result = run_living_cycle(
            domain=kstate.last_domain, tick=kstate.tick + 1, dry_run=not args.live,
        )
        print(json.dumps(result, indent=2))
        return 0

    if args.lab_trading:
        from oss.lab.trading_strategy import trading_lab_comparison
        print(json.dumps(trading_lab_comparison(dry_run=not args.live), indent=2))
        return 0

    if args.lab_saas:
        from oss.lab.saas_product import saas_lab_comparison
        print(json.dumps(
            saas_lab_comparison(
                dry_run=not args.live,
                cycles=args.lab_cycles,
                use_adapter=True,
            ),
            indent=2,
        ))
        return 0

    if args.status:
        print(json.dumps(kernel_status(), indent=2))
        return 0

    dry = not args.live
    results = []
    for _ in range(max(1, args.ticks)):
        results.append(tick(dry_run=dry).to_dict())
    print(json.dumps(results[-1] if len(results) == 1 else results, indent=2))
    return 0 if results[-1].get("all_ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())