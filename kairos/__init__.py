"""
kairos — KAIROS/SAGE Self-Improvement Engine for GH05T3/Aethyro
================================================================
Packages:
  kairos.py          — KAIROS 6-phase state machine
  verification.py    — 3-gate verification pipeline (Ethics/Sim/CLARA)
  meta_agent.py      — Meta-Agent: rewrites improvement rules every 3 cycles
  gitops_mutator.py  — Headless local Git-Ops mutation pipeline
  sage_loop.py       — SAGE Self-Improvement Engine (nightly scheduler)
  honcho_api.py      — FastAPI/WebSocket API for Honcho dashboard
"""
from .kairos import KAIROSEngine, KAIROSPhase, KAIROSPlan
from .sage_loop import SAGELoop, run_sage_loop_service
from .verification import VerificationPipeline, VerificationResult

__all__ = [
    "KAIROSEngine", "KAIROSPhase", "KAIROSPlan",
    "SAGELoop", "run_sage_loop_service",
    "VerificationPipeline", "VerificationResult",
]
