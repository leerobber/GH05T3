from __future__ import annotations

import logging
import sys
from pathlib import Path

LOG = logging.getLogger("oss.adapter.evolution")

_BACKEND = Path(__file__).resolve().parents[2] / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


def record_swarm_cycle(
    proposal: str,
    score: float,
    agent_ids: list[str],
    verdict: str = "PASS",
) -> dict:
    """Record Omni-Mind swarm outcome in KAIROS."""
    try:
        from evolution.kairos import record_cycle
        return record_cycle(
            proposal=proposal[:500],
            verdict=verdict if score >= 0.5 else "FAIL",
            score=score,
            agent_id=",".join(agent_ids[:3]),
        )
    except Exception as exc:
        LOG.warning("KAIROS record failed: %s", exc)
        return {"id": None, "score": score, "error": str(exc)}