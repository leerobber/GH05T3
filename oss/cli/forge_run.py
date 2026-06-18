#!/usr/bin/env python3
"""Run one Omni Forge agency curation cycle from the CLI."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from oss.forge.agency import get_agency
from oss.forge.schemas import QualityTier


def main() -> int:
    ap = argparse.ArgumentParser(description="Omni Forge agency curation cycle")
    ap.add_argument("--min-tier", default="silver", choices=[t.value for t in QualityTier])
    ap.add_argument("--no-pipeline", action="store_true")
    ap.add_argument("--no-seeds", action="store_true")
    ap.add_argument("--no-export", action="store_true")
    ap.add_argument("--status", action="store_true", help="print forge status only")
    args = ap.parse_args()

    agency = get_agency()
    if args.status:
        print(json.dumps(agency.status(), indent=2))
        return 0

    record = agency.run_cycle(
        include_pipeline=not args.no_pipeline,
        include_seeds=not args.no_seeds,
        min_tier=QualityTier(args.min_tier),
        export=not args.no_export,
    )
    print(json.dumps(record.to_dict(), indent=2))
    return 0 if record.kept > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())