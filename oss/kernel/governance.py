"""Constitution engine — alignment, constraints, runaway prevention."""
from __future__ import annotations

import logging
from typing import Any

LOG = logging.getLogger("oss.kernel.governance")

# Actions the autonomous kernel may never take without human gate
HUMAN_GATE_ACTIONS = frozenset({
    "wire_real_funds",
    "deploy_production_billing",
    "modify_killswitch",
    "modify_strange_loop",
    "external_wallet_transfer",
    "strip_customer_data",
})

SACRED_PATHS = frozenset({
    "backend/security/ghost_protocol.py",
    "backend/core/omega_loop.py",
})


def preflight() -> dict[str, Any]:
    from oss.train.constitution import RULES, constitution_report

    report = constitution_report()
    return {
        "pillar": "constitution_engine",
        "rules": list(RULES),
        "training_ready": report.get("ready", False),
        "human_gates": sorted(HUMAN_GATE_ACTIONS),
        "sacred_paths": sorted(SACRED_PATHS),
    }


def authorize_action(action: str, *, context: dict[str, Any] | None = None) -> tuple[bool, str]:
    """Return (allowed, reason). Autonomous tick may only run safe actions."""
    if action in HUMAN_GATE_ACTIONS:
        return False, f"{action} requires Robert approval"
    ctx = context or {}
    if ctx.get("touches_sacred"):
        return False, "sacred subsystem — human gate required"
    return True, "ok"


def evaluate_tick_budget(
    *,
    proposed_spend: float,
    treasury_balance: float,
    max_spend_pct: float = 0.15,
) -> tuple[bool, str]:
    if treasury_balance <= 0:
        return True, "dry treasury — spend deferred"
    cap = treasury_balance * max_spend_pct
    if proposed_spend > cap:
        return False, f"spend {proposed_spend:.2f} exceeds tick cap {cap:.2f}"
    return True, "ok"