"""Sovereign economy bridge — unifies local NC with external economy APIs."""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any

import httpx

from oss.schemas.economy import CreditSource, EconomySnapshot

LOG = logging.getLogger("oss.adapter.sovereign")

_ROOT = Path(__file__).resolve().parents[2]
_BACKEND = _ROOT / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def economy_api_url() -> str:
    return os.environ.get("ECONOMY_API_URL", "http://localhost:8081").rstrip("/")


def sovereign_core_url() -> str:
    return os.environ.get("SOVEREIGN_CORE_URL", "http://localhost:9000").rstrip("/")


def external_economy_available(timeout: float = 2.0) -> bool:
    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.get(f"{economy_api_url()}/")
            return r.status_code < 500
    except Exception:
        return False


def sovereign_core_available(timeout: float = 2.0) -> bool:
    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.get(f"{sovereign_core_url()}/health")
            return r.status_code == 200
    except Exception:
        return False


def fetch_external_economy_stats(timeout: float = 3.0) -> dict[str, Any]:
    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.get(f"{economy_api_url()}/system/stats")
            if r.status_code == 200:
                return r.json()
    except Exception as exc:
        LOG.debug("external economy stats unavailable: %s", exc)
    return {}


def fetch_sovereign_health(timeout: float = 3.0) -> dict[str, Any]:
    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.get(f"{sovereign_core_url()}/health")
            if r.status_code == 200:
                return r.json()
    except Exception as exc:
        LOG.debug("sovereign core health unavailable: %s", exc)
    return {"status": "unreachable"}


def credit_agent(name: str, amount: float, reason: str) -> bool:
    """Post credits to local ledger and external economy when available."""
    if amount <= 0:
        return False
    try:
        import economy_bridge
        return bool(economy_bridge._seed(name, int(amount), reason))
    except Exception as exc:
        LOG.warning("credit_agent failed for %s: %s", name, exc)
        try:
            from economy.ledger import get_ledger
            get_ledger().credit(name, amount, reason, source=CreditSource.SOVEREIGN_ECONOMY.value)
            return True
        except Exception:
            return False


def unified_economy_snapshot() -> EconomySnapshot:
    """Merge local Platform Credits, marketplace, and external economy status."""
    from oss.economy.neuro_coin import get_neuro_coin
    from oss.adapters.marketplace import list_jobs

    nc = get_neuro_coin()
    local_stats = nc.stats()
    balances = nc.all_balances()
    external = fetch_external_economy_stats()
    sovereign = fetch_sovereign_health()

    external_online = external_economy_available()
    core_online = sovereign_core_available() and sovereign.get("status") != "unreachable"

    total_balance = sum(balances.values()) if balances else 0.0
    pending = len(list_jobs(status="pending", limit=200))

    ext_agents = 0
    if external:
        agents_block = external.get("agents") or {}
        if isinstance(agents_block, dict):
            ext_agents = int(agents_block.get("total", 0) or 0)

    return EconomySnapshot(
        currency=nc.CURRENCY,
        local_online=True,
        external_economy_online=external_online,
        sovereign_core_online=core_online,
        total_agents=max(len(balances), ext_agents),
        total_balance=total_balance,
        pending_jobs=pending,
        local_balances=balances,
        external_stats=external or {"status": "offline"},
        sovereign_health=sovereign,
    )