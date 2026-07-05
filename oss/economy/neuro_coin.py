"""Neuro-Coin — unified economy over ledger + marketplace."""
from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_BACKEND = Path(__file__).resolve().parents[2] / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

_neuro: NeuroCoin | None = None


@dataclass
class NeuroTx:
    agent_id: str
    amount: float
    balance: float
    reason: str
    source: str


class NeuroCoin:
    """Neuro-Coin wallet — wraps economy/ledger + marketplace rewards."""

    CURRENCY = "NC"

    def __init__(self) -> None:
        from economy.ledger import get_ledger
        self._ledger = get_ledger()

    def balance(self, agent_id: str) -> float:
        return self._ledger.balance(agent_id)

    def earn(self, agent_id: str, amount: float, reason: str = "") -> float:
        return self._ledger.credit(agent_id, amount, reason, source="neuro_coin")

    def spend(self, agent_id: str, amount: float, reason: str = "") -> float:
        return self._ledger.debit(agent_id, amount, reason, source="neuro_coin")

    def transfer(self, from_id: str, to_id: str, amount: float, reason: str = "") -> dict:
        if amount <= 0:
            raise ValueError("transfer amount must be positive")
        if self.balance(from_id) < amount:
            raise ValueError(f"insufficient balance: {self.balance(from_id)} < {amount}")
        self.spend(from_id, amount, f"transfer to {to_id}: {reason}")
        new_bal = self.earn(to_id, amount, f"transfer from {from_id}: {reason}")
        return {"from": from_id, "to": to_id, "amount": amount, "to_balance": new_bal}

    def all_balances(self) -> dict[str, float]:
        return self._ledger.all_balances()

    def history(self, agent_id: str, limit: int = 50) -> list:
        return self._ledger.history(agent_id, limit=limit)

    def stats(self) -> dict[str, Any]:
        base = self._ledger.stats()
        base["currency"] = self.CURRENCY
        return base

    async def post_job(
        self,
        task: str,
        tags: list[str] | None = None,
        reward: int = 20,
        posted_by: str = "neuro_coin",
    ) -> str:
        from oss.adapters.marketplace import post_job
        return await post_job(task=task, tags=tags, reward=reward, posted_by=posted_by)

    async def reward_job_completion(self, agent_id: str, reward: int, job_id: str) -> float:
        return self.earn(agent_id, float(reward), reason=f"job {job_id} completed")


def get_neuro_coin() -> NeuroCoin:
    global _neuro
    if _neuro is None:
        _neuro = NeuroCoin()
    return _neuro