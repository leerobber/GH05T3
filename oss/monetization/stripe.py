"""Stripe → Platform Credits (NC) settlement facade."""
from __future__ import annotations

import logging
import sys
import time
from pathlib import Path
from typing import Any

_BACKEND = Path(__file__).resolve().parents[2] / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from oss.adapters.sovereign import credit_agent

LOG = logging.getLogger("oss.monetization.stripe")

PLAN_CREDITS: dict[str, int] = {
    "starter": 100,
    "pro": 500,
    "enterprise": 2000,
}

DEFAULT_AGENT = "GH05T3-Avery"

PLAN_AGENT_MAP: dict[str, str] = {
    "starter": DEFAULT_AGENT,
    "pro": DEFAULT_AGENT,
    "enterprise": DEFAULT_AGENT,
}

_MAX_HISTORY = 100
_settlements: list[dict[str, Any]] = []


def _normalize_plan(plan: str | None) -> str:
    key = (plan or "starter").strip().lower()
    if key in PLAN_CREDITS:
        return key
    for alias, canonical in (
        ("basic", "starter"),
        ("standard", "pro"),
        ("premium", "pro"),
        ("business", "enterprise"),
    ):
        if alias in key:
            return canonical
    return "starter"


def _get_subscriber_record(customer_id: str | None) -> dict | None:
    """Load subscriber from backend stripe integration (namespace-safe)."""
    if not customer_id:
        return None
    try:
        import importlib.util

        mod_path = _BACKEND / "integrations" / "stripe_integration.py"
        spec = importlib.util.spec_from_file_location(
            "gh05t3_backend_stripe_integration",
            mod_path,
        )
        if spec is None or spec.loader is None:
            return None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        sub = mod.get_subscriber(customer_id)
        return sub if isinstance(sub, dict) else None
    except Exception as exc:
        LOG.debug("subscriber lookup failed for %s: %s", customer_id, exc)
        return None


def _resolve_agent(customer_id: str | None, plan: str) -> str:
    """Map subscriber to credited agent; defaults to GH05T3-Avery."""
    sub = _get_subscriber_record(customer_id)
    if sub:
        agent = sub.get("agent") or sub.get("credit_agent")
        if agent:
            return str(agent)
        plan = _normalize_plan(sub.get("plan") or plan)
    return PLAN_AGENT_MAP.get(plan, DEFAULT_AGENT)


def _lookup_plan(customer_id: str | None) -> str:
    sub = _get_subscriber_record(customer_id)
    if sub:
        return _normalize_plan(sub.get("plan"))
    return "starter"


def _record_settlement(entry: dict[str, Any]) -> None:
    global _settlements
    _settlements.append(entry)
    if len(_settlements) > _MAX_HISTORY:
        _settlements = _settlements[-_MAX_HISTORY:]


def settle_payment(
    customer_id: str | None,
    amount_usd: float,
    plan: str | None,
    event_type: str,
) -> dict[str, Any]:
    """Credit NC to GH05T3-Avery or mapped agent for a Stripe payment event."""
    plan_key = _normalize_plan(plan)
    credits = PLAN_CREDITS[plan_key]
    agent = _resolve_agent(customer_id, plan_key)
    reason = (
        f"stripe:{event_type}:customer={customer_id or 'unknown'}"
        f":plan={plan_key}:usd={amount_usd:.2f}"
    )

    credited = credit_agent(agent, float(credits), reason)
    entry = {
        "ok": credited,
        "customer_id": customer_id,
        "amount_usd": round(float(amount_usd or 0), 2),
        "plan": plan_key,
        "credits": credits,
        "agent": agent,
        "event_type": event_type,
        "reason": reason,
        "ts": time.time(),
    }
    _record_settlement(entry)
    if credited:
        LOG.info(
            "Settled %s NC to %s for customer %s (%s)",
            credits,
            agent,
            customer_id,
            event_type,
        )
    else:
        LOG.warning(
            "Settlement failed for customer %s (%s, %s NC)",
            customer_id,
            event_type,
            credits,
        )
    return entry


def settle_invoice_payment(data: dict[str, Any]) -> dict[str, Any]:
    """Wrapper for invoice.payment_succeeded webhook payloads."""
    inv = data.get("object", data) if isinstance(data, dict) else {}
    customer_id = inv.get("customer")
    amount_usd = float(inv.get("amount_paid", 0) or 0) / 100.0
    plan = _lookup_plan(customer_id)
    return settle_payment(customer_id, amount_usd, plan, "invoice.payment_succeeded")


def settlement_status() -> dict[str, Any]:
    """Recent settlement stats (in-memory, max 100 entries)."""
    recent = list(_settlements)
    ok_count = sum(1 for s in recent if s.get("ok"))
    failed = len(recent) - ok_count
    total_credits = sum(s.get("credits", 0) for s in recent if s.get("ok"))
    return {
        "total": len(recent),
        "ok": ok_count,
        "failed": failed,
        "total_credits_settled": total_credits,
        "plan_credits": dict(PLAN_CREDITS),
        "recent": recent[-20:],
    }


def clear_settlements() -> None:
    """Test helper — reset in-memory settlement history."""
    global _settlements
    _settlements = []