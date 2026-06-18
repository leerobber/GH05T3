#!/usr/bin/env python3
"""OSS Sprint 1 milestone — Omni-DNA swarm solve demo."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from oss.mind.omni_mind import get_mind
from oss.schemas.genome import SwarmTask


DEFAULT_PROBLEM = (
    "Design a 3-step plan to reduce gateway latency on port 8002 "
    "without removing authentication."
)


async def main() -> int:
    parser = argparse.ArgumentParser(description="OSS Omni-Mind swarm demo")
    parser.add_argument("--seed-only", action="store_true", help="Bootstrap genomes and exit")
    parser.add_argument("--problem", default=DEFAULT_PROBLEM)
    parser.add_argument("--traits", nargs="*", default=["coding", "self_reflection"])
    parser.add_argument("--max-agents", type=int, default=3)
    args = parser.parse_args()

    mind = get_mind()
    count = mind.bootstrap()
    print(f"Genomes loaded: {count}")

    if args.seed_only:
        for a in mind.state()["agents"]:
            traits = ", ".join(f"{k}={v}" for k, v in a["traits"].items())
            print(f"  {a['genome_id']} ({a['display_name']}): {traits}")
        return 0

    task = SwarmTask(
        problem=args.problem,
        required_traits=args.traits,
        max_agents=args.max_agents,
    )
    print(f"\nSwarm task: {task.problem[:120]}...")
    print(f"Required traits: {task.required_traits}\n")

    result = await mind.solve_with_swarm(task)
    print("=" * 60)
    print(f"Task ID:    {result.task_id}")
    print(f"Agents:     {', '.join(result.agents)}")
    print(f"Score:      {result.score}")
    print(f"KAIROS ID:  {result.kairos_cycle_id}")
    print(f"Trait deltas: {json.dumps(result.trait_deltas, indent=2)}")
    print("-" * 60)
    print(result.synthesis[:3000])
    print("=" * 60)
    return 0 if result.synthesis else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))