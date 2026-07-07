"""Aetherflux expert fitness bridge (passive registration only).

Turns aetherflux-zero's measured per-domain routing stats (see
leerobber/aetherflux-zero's examples/specialist_pilot.rs, run separately --
this repo has no Rust toolchain dependency of its own) into real fitness
scores on real ChronosLedger agent slots (backend/oss/core/chronos_ledger.py).

Why `recall` and not an arbitrary reward/credit unit: ChronosLedger.fitness
is documented and enforced to live in [0,1] (_f16 clips silently). A domain's
held-out routing recall (fraction of its own held-out text the router
actually recognized as belonging to it) is already bounded in [0,1] by
construction -- no invented conversion factor needed.

**Deliberately passive, not wired into GenesisThread/AethyroBridge.**
Investigated directly before writing this: GenesisThread's real dissent/
spawn/prune loop only evaluates agents registered in an external
`swarm.agents` dict (backend/oss/genomic/agents.py's `AgentSwarm`), whose
`Agent.act(task, ...)` unit of work is executing curriculum tasks
(persuasion copy, funnel analysis, trade evaluation) scored by breakthrough/
novelty/desire-fulfillment. A ternary text-domain router expert doesn't
perform tasks in that sense -- there's no honest, non-fabricated way to make
it a real participant in that loop without inventing fake task-execution
behavior for it. So this module only ever registers/updates ledger slots
directly (bypassing AethyroBridge's in-memory `_slots`/`sync_agent` path
entirely) -- these agents will never be dissent-evaluated, spawned, or
pruned, by design. They *do* still contribute to `desires_matrix()`'s
population mean (any occupied slot does), which is exactly why `desires`
is left at a neutral 0.5 across all seven dimensions here: a neutral vector
pulls the centroid in no particular direction, unlike a fabricated one would.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from backend.oss.core.chronos_ledger import SCRATCH_NEEDS_REVIEW, ChronosLedger, get_chronos_ledger

_DEFAULT_SLOT_MAP_PATH = Path(__file__).resolve().parents[3] / "data" / "aetherflux_slots.json"


@dataclass
class BridgeResult:
    name: str
    slot: int
    action: str  # "registered" or "updated"
    fitness_written: float
    needs_review: bool


def _load_slot_map(path: Path) -> dict[str, int]:
    if not path.is_file():
        return {}
    with open(path) as f:
        return json.load(f)


def _save_slot_map(path: Path, slot_map: dict[str, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(slot_map, f, indent=2, sort_keys=True)


def register_or_update_experts(
    ledger: Optional[ChronosLedger],
    export_path: str,
    slot_map_path: Path = _DEFAULT_SLOT_MAP_PATH,
    live: bool = False,
) -> list[BridgeResult]:
    """Reads a specialist_pilot JSON export and registers/updates one
    passive ChronosLedger agent slot per domain, using `recall` as the
    fitness value. See module docstring for why this is deliberately NOT
    wired into GenesisThread's dissent/spawn/prune loop.

    `live=False` (the default): computes and returns what WOULD be written,
    without opening the ledger for any mutating call. `live=True` performs
    the real `write_at_next_available_slot`/`update_fitness`/
    `set_scratch_bit`/`clear_scratch_bit` calls.

    Idempotent across repeated runs via `slot_map_path`, same reasoning as
    the GH05T3-Sovereign BinaryLedger bridge this was ported from.
    """
    with open(export_path) as f:
        export = json.load(f)

    slot_map = _load_slot_map(slot_map_path)
    results: list[BridgeResult] = []

    for domain in export["domains"]:
        name = domain["name"]
        recall = float(domain["recall"])
        needs_review = not bool(domain["specialized"])

        if name in slot_map:
            slot = slot_map[name]
            action = "updated"
        else:
            slot = None
            action = "registered"

        if not live:
            results.append(BridgeResult(name=name, slot=slot if slot is not None else -1, action=f"{action} (dry-run)", fitness_written=recall, needs_review=needs_review))
            continue

        if action == "registered":
            slot = ledger.write_at_next_available_slot(desires=(0.5,) * 7, maturity=1, fitness=recall, generation=0)
            slot_map[name] = slot
        else:
            ledger.update_fitness(slot, recall)

        if needs_review:
            ledger.set_scratch_bit(slot, SCRATCH_NEEDS_REVIEW)
        else:
            ledger.clear_scratch_bit(slot, SCRATCH_NEEDS_REVIEW)

        results.append(BridgeResult(name=name, slot=slot, action=action, fitness_written=recall, needs_review=needs_review))

    if live:
        _save_slot_map(slot_map_path, slot_map)

    return results


def _print_report(results: list[BridgeResult], live: bool) -> None:
    mode = "LIVE" if live else "DRY-RUN"
    print(f"--- aetherflux expert fitness bridge ({mode}) -- passive registration only, not wired into GenesisThread ---")
    for r in results:
        slot_str = str(r.slot) if r.slot >= 0 else "(new)"
        flag = " [NEEDS_REVIEW]" if r.needs_review else ""
        print(f"  slot={slot_str:>6}  {r.action:<20}  fitness={r.fitness_written:.4f}{flag}  {r.name}")
    if not live:
        print("\n  dry-run only -- no ledger writes performed. Re-run with --live to actually write.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="path to specialist_pilot's JSON export")
    parser.add_argument("--live", action="store_true", help="actually write to the ledger (default: dry-run)")
    parser.add_argument("--slot-map", default=str(_DEFAULT_SLOT_MAP_PATH), help="path to the domain->slot side file")
    args = parser.parse_args(argv)

    if not os.path.isfile(args.input):
        print(f"error: export file not found: {args.input}", file=sys.stderr)
        return 1

    ledger = get_chronos_ledger() if args.live else None
    results = register_or_update_experts(
        ledger,
        args.input,
        slot_map_path=Path(args.slot_map),
        live=args.live,
    )
    if ledger is not None:
        ledger.flush()  # singleton stays open (matches genesis_thread.py's own lifecycle); just ensure durability

    _print_report(results, args.live)
    return 0


if __name__ == "__main__":
    sys.exit(main())
