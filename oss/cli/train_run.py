#!/usr/bin/env python3
"""Sovereign Train CLI — agent-native fine-tuning without TRL."""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from oss.train.constitution import ConstitutionViolation, constitution_report
from oss.train.engine import run_training
from oss.train.schemas import TrainConfig, TrainJob, TrainSource

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)


def main() -> int:
    ap = argparse.ArgumentParser(description="Sovereign Train Kernel")
    ap.add_argument("--agent", default="GH05T3", help="Agent ID (GH05T3, FORGE, ORACLE, ...)")
    ap.add_argument("--steps", type=int, default=80)
    ap.add_argument("--model", default="Qwen/Qwen2.5-Coder-3B-Instruct")
    ap.add_argument("--output", default=None, help="Adapter output directory")
    ap.add_argument("--batch", type=int, default=1)
    ap.add_argument("--grad-accum", type=int, default=8)
    ap.add_argument("--max-seq-len", type=int, default=512)
    ap.add_argument("--lr", type=float, default=2e-5)
    ap.add_argument("--forge-only", action="store_true", help="Forge gold + elite only")
    ap.add_argument("--all-sources", action="store_true", help="Forge + elite + agent JSONL")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--preflight", action="store_true")
    ap.add_argument("--list-agents", action="store_true")
    args = ap.parse_args()

    if args.preflight:
        print(json.dumps(constitution_report(), indent=2))
        return 0

    if args.list_agents:
        from oss.train.agents import list_agents
        print(json.dumps(list_agents(), indent=2))
        return 0

    sources = [TrainSource.ALL] if args.all_sources else (
        [TrainSource.FORGE, TrainSource.ELITE] if args.forge_only else
        [TrainSource.FORGE, TrainSource.ELITE, TrainSource.AGENT_FILES]
    )

    job = TrainJob(
        agent_id=args.agent,
        output_dir=Path(args.output) if args.output else None,
        dry_run=args.dry_run,
        config=TrainConfig(
            model_id=args.model,
            max_steps=args.steps,
            batch_size=args.batch,
            grad_accum=args.grad_accum,
            max_seq_len=args.max_seq_len,
            learning_rate=args.lr,
            sources=sources,
        ),
    )

    try:
        result = run_training(job)
        print(json.dumps(result.to_dict(), indent=2))
        return 0 if result.success else 1
    except ConstitutionViolation as exc:
        print(json.dumps({"success": False, "error": str(exc)}, indent=2))
        return 1
    except Exception as exc:
        logging.exception("train failed")
        print(json.dumps({"success": False, "error": str(exc)}, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())