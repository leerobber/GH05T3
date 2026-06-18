"""Credit Layer — Platform Credits (NC) and ledger event contracts."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CreditSource(str, Enum):
    LOCAL = "local"
    NEURO_COIN = "neuro_coin"
    MARKETPLACE = "marketplace"
    SOVEREIGN_ECONOMY = "sovereign_economy"
    SOVEREIGN_CORE = "sovereign_core"
    TRAINING = "training"
    STRIPE = "stripe"


class CreditEventType(str, Enum):
    CREDIT = "credit"
    DEBIT = "debit"
    TRANSFER = "transfer"
    JOB_REWARD = "job_reward"
    JOB_POST = "job_post"


@dataclass
class CreditEvent:
    """Immutable ledger event — mirrors economy/ledger credit_transactions."""

    agent_id: str
    delta: float
    balance: float
    reason: str = ""
    source: CreditSource = CreditSource.LOCAL
    event_type: CreditEventType = CreditEventType.CREDIT
    timestamp: float = 0.0
    event_id: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.event_id,
            "ts": self.timestamp,
            "agent_id": self.agent_id,
            "delta": self.delta,
            "balance": self.balance,
            "reason": self.reason,
            "source": self.source.value,
            "event_type": self.event_type.value,
        }

    @classmethod
    def from_ledger_row(cls, row: dict[str, Any] | Any) -> CreditEvent:
        if hasattr(row, "keys"):
            data = dict(row)
        else:
            data = {
                "id": row[0] if len(row) > 0 else None,
                "ts": row[1] if len(row) > 1 else 0.0,
                "agent_id": row[2] if len(row) > 2 else "",
                "delta": row[3] if len(row) > 3 else 0.0,
                "balance": row[4] if len(row) > 4 else 0.0,
                "reason": row[5] if len(row) > 5 else "",
                "source": row[6] if len(row) > 6 else CreditSource.LOCAL.value,
            }
        raw_source = str(data.get("source", CreditSource.LOCAL.value))
        try:
            source = CreditSource(raw_source)
        except ValueError:
            source = CreditSource.LOCAL
        delta = float(data.get("delta", 0.0))
        event_type = CreditEventType.DEBIT if delta < 0 else CreditEventType.CREDIT
        return cls(
            event_id=data.get("id"),
            timestamp=float(data.get("ts", 0.0)),
            agent_id=str(data.get("agent_id", "")),
            delta=delta,
            balance=float(data.get("balance", 0.0)),
            reason=str(data.get("reason", "")),
            source=source,
            event_type=event_type,
        )


@dataclass
class EconomySnapshot:
    """Unified view across local NC, marketplace, and external economy APIs."""

    currency: str = "NC"
    local_online: bool = True
    external_economy_online: bool = False
    sovereign_core_online: bool = False
    total_agents: int = 0
    total_balance: float = 0.0
    pending_jobs: int = 0
    local_balances: dict[str, float] = field(default_factory=dict)
    external_stats: dict[str, Any] = field(default_factory=dict)
    sovereign_health: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "currency": self.currency,
            "local_online": self.local_online,
            "external_economy_online": self.external_economy_online,
            "sovereign_core_online": self.sovereign_core_online,
            "total_agents": self.total_agents,
            "total_balance": round(self.total_balance, 4),
            "pending_jobs": self.pending_jobs,
            "local_balances": self.local_balances,
            "external_stats": self.external_stats,
            "sovereign_health": self.sovereign_health,
        }