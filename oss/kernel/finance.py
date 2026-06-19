"""Finance engine — opportunities, revenue, investment allocation."""
from __future__ import annotations

import logging
from typing import Any

LOG = logging.getLogger("oss.kernel.finance")

REVENUE_STREAMS = (
    "saas_tools",
    "api_access",
    "microservices",
    "model_licensing",
    "dataset_sales",
    "digital_assets",
    "marketplace_fees",
    "research_services",
)


def economy_snapshot() -> dict[str, Any]:
    try:
        from oss.adapters.sovereign import unified_economy_snapshot
        snap = unified_economy_snapshot()
        return snap.to_dict()
    except Exception as exc:
        return {"error": str(exc), "local_online": False}


def estimate_tick_revenue(*, tick: int, dry_run: bool = True) -> float:
    """Heuristic revenue model until live Stripe/NC flows attach."""
    if dry_run:
        return 0.0
    base = 5.0 + (tick % 7) * 2.5
    try:
        snap = economy_snapshot()
        pending = int(snap.get("pending_jobs", 0))
        return base + pending * 0.5
    except Exception:
        return base


def investment_scan(*, treasury_balance: float) -> dict[str, Any]:
    """Rank yield opportunities — stubs for staking/LP/micro-VC."""
    opportunities = []
    if treasury_balance > 500:
        opportunities.append({
            "id": "compute_reserve",
            "type": "infrastructure",
            "expected_yield": 0.0,
            "risk": "low",
            "note": "Fund GPU hours for training + inference",
        })
    if treasury_balance > 200:
        opportunities.append({
            "id": "agent_payroll_pool",
            "type": "labor_credits",
            "expected_yield": 0.15,
            "risk": "medium",
            "note": "NC credits to ORACLE/FORGE/NEXUS for marketplace jobs",
        })
    return {"balance": treasury_balance, "opportunities": opportunities}