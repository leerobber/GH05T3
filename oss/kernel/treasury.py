"""Treasury — reserves, allocation, reinvestment."""
from __future__ import annotations

import logging
from typing import Any

from oss.kernel.schemas import TreasuryPolicy

LOG = logging.getLogger("oss.kernel.treasury")

TREASURY_AGENT = "SOVEREIGN_TREASURY"


def treasury_balance() -> float:
    try:
        from oss.economy.neuro_coin import get_neuro_coin
        return get_neuro_coin().balance(TREASURY_AGENT)
    except Exception:
        return 0.0


def ensure_treasury_seeded(min_balance: float = 1000.0) -> float:
    bal = treasury_balance()
    if bal >= min_balance:
        return bal
    try:
        from oss.adapters.sovereign import credit_agent
        credit_agent(TREASURY_AGENT, min_balance - bal, "kernel treasury seed")
        return treasury_balance()
    except Exception as exc:
        LOG.debug("treasury seed skipped: %s", exc)
        return bal


def allocate_inflow(
    amount: float,
    policy: TreasuryPolicy | None = None,
    *,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Split revenue across reserve, research, compute, payroll, risk."""
    policy = policy or TreasuryPolicy()
    policy.validate()
    if amount <= 0:
        return {"amount": 0.0, "buckets": {}}

    buckets = {
        "reserve": round(amount * policy.reserve_pct, 4),
        "research": round(amount * policy.research_pct, 4),
        "compute": round(amount * policy.compute_pct, 4),
        "agent_payroll": round(amount * policy.agent_payroll_pct, 4),
        "risk_buffer": round(amount * policy.risk_buffer_pct, 4),
    }
    result: dict[str, Any] = {"amount": amount, "buckets": buckets, "dry_run": dry_run}

    if dry_run:
        return result

    try:
        from oss.economy.neuro_coin import get_neuro_coin
        nc = get_neuro_coin()
        for bucket, slice_amt in buckets.items():
            if slice_amt > 0:
                nc.earn(f"TREASURY_{bucket.upper()}", slice_amt, f"allocate from {TREASURY_AGENT}")
    except Exception as exc:
        result["error"] = str(exc)
    return result


def fund_agent(agent_id: str, amount: float, reason: str, *, dry_run: bool = True) -> bool:
    if dry_run or amount <= 0:
        return dry_run
    try:
        from oss.economy.neuro_coin import get_neuro_coin
        nc = get_neuro_coin()
        if nc.balance(TREASURY_AGENT) < amount:
            return False
        nc.spend(TREASURY_AGENT, amount, f"fund {agent_id}: {reason}")
        nc.earn(agent_id, amount, reason)
        return True
    except Exception as exc:
        LOG.warning("fund_agent failed: %s", exc)
        return False