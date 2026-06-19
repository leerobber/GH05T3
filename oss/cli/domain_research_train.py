#!/usr/bin/env python3
"""Domain Research Training — Rob rotation domains + SPIN + sovereign_nation."""
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
from oss.train.domain_research import (
    ROB_DOMAIN_SLUGS,
    DomainResearchConfig,
    build_domain_research_dataset,
)
from oss.train.engine import run_domain_research_training
from oss.train.schemas import TrainConfig, TrainJob

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")


def main() -> int:
    ap = argparse.ArgumentParser(description="GH05T3 Domain Research Training (Rob domains)")
    ap.add_argument("--agent", default="GH05T3")
    ap.add_argument("--steps", type=int, default=300)
    ap.add_argument("--model", default="Qwen/Qwen2.5-Coder-3B-Instruct")
    ap.add_argument("--output", default="backend/models/domain_research_adapter")
    ap.add_argument("--goals-per-domain", type=int, default=12)
    ap.add_argument("--spin-cap", type=int, default=400)
    ap.add_argument("--batch", type=int, default=1)
    ap.add_argument("--grad-accum", type=int, default=8)
    ap.add_argument("--max-seq-len", type=int, default=768)
    ap.add_argument("--gpu-frac", type=float, default=0.55)
    ap.add_argument("--domains", default=None, help="Comma-separated slugs (default: Rob rotation)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--preflight", action="store_true")
    ap.add_argument("--manifest-only", action="store_true")
    args = ap.parse_args()

    if args.preflight:
        print(json.dumps(constitution_report(), indent=2))
        return 0

    slugs = tuple(s.strip() for s in args.domains.split(",") if s.strip()) if args.domains else ROB_DOMAIN_SLUGS
    dcfg = DomainResearchConfig(
        domain_slugs=slugs,
        goals_per_domain=args.goals_per_domain,
        spin_cap=args.spin_cap,
    )

    if args.manifest_only or args.dry_run:
        _, manifest = build_domain_research_dataset(dcfg)
        print(json.dumps(manifest, indent=2))
        if args.manifest_only:
            return 0

    job = TrainJob(
        agent_id=args.agent,
        output_dir=Path(args.output),
        dry_run=args.dry_run,
        config=TrainConfig(
            model_id=args.model,
            max_steps=args.steps,
            batch_size=args.batch,
            grad_accum=args.grad_accum,
            max_seq_len=args.max_seq_len,
            gpu_memory_frac=args.gpu_frac,
        ),
    )

    try:
        result = run_domain_research_training(job, dcfg)
        print(json.dumps(result.to_dict(), indent=2))
        return 0 if result.success else 1
    except ConstitutionViolation as exc:
        print(json.dumps({"success": False, "error": str(exc)}, indent=2))
        return 1
    except Exception as exc:
        logging.exception("domain research train failed")
        print(json.dumps({"success": False, "error": str(exc)}, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())