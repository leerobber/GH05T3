"""ValueFlowEngine — Omni-Economy circulatory system."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TraitListing:
    genome_id: str
    trait_name: str
    price_nc: float
    listing_id: str = field(default_factory=lambda: f"trait_{uuid.uuid4().hex[:8]}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "listing_id": self.listing_id,
            "genome_id": self.genome_id,
            "trait_name": self.trait_name,
            "price_nc": self.price_nc,
        }


@dataclass
class MemoryListing:
    genome_id: str
    memory_type: str
    summary: str
    price_nc: float
    listing_id: str = field(default_factory=lambda: f"mem_{uuid.uuid4().hex[:8]}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "listing_id": self.listing_id,
            "genome_id": self.genome_id,
            "memory_type": self.memory_type,
            "summary": self.summary[:120],
            "price_nc": self.price_nc,
        }


@dataclass
class Bounty:
    goal_id: str
    description: str
    reward_nc: float
    quantum_flag: bool = False
    status: str = "open"
    assignees: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal_id": self.goal_id,
            "description": self.description,
            "reward_nc": self.reward_nc,
            "quantum_flag": self.quantum_flag,
            "status": self.status,
            "assignees": self.assignees,
        }


@dataclass
class SoulBond:
    agent_id: str
    strength: float
    since_ts: float
    perks: tuple[str, ...] = ("priority_swarm", "reduced_fees")

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "strength": round(self.strength, 4),
            "since_ts": self.since_ts,
            "perks": list(self.perks),
        }


class ValueFlowEngine:
    """Neuro-Coins + markets + bounties + soul bonds — one economic kernel."""

    def __init__(self) -> None:
        self.trait_marketplace: list[TraitListing] = []
        self.memory_marketplace: list[MemoryListing] = []
        self.bounties: dict[str, Bounty] = {}
        self.soul_bonds: dict[str, SoulBond] = {}
        self.transaction_history: list[dict[str, Any]] = []

    def earn(self, agent_id: str, amount: float, reason: str = "") -> float:
        try:
            from oss.economy.neuro_coin import get_neuro_coin
            bal = get_neuro_coin().earn(agent_id, amount, reason)
            self._log("earn", agent_id, amount, reason)
            return bal
        except Exception:
            self._log("earn_sim", agent_id, amount, reason)
            return amount

    def balance(self, agent_id: str) -> float:
        try:
            from oss.economy.neuro_coin import get_neuro_coin
            return get_neuro_coin().balance(agent_id)
        except Exception:
            return 0.0

    def ddrs_reward(self, agent_id: str, task: dict[str, Any]) -> dict[str, Any]:
        try:
            from oss.economy.desire import get_desire_system
            return get_desire_system().reward_agent(agent_id, task)
        except Exception:
            return {"mode": "sim", "neuro_coin_reward": task.get("reward", 5)}

    def list_trait(self, genome_id: str, trait_name: str, price_nc: float) -> TraitListing:
        listing = TraitListing(genome_id, trait_name, price_nc)
        self.trait_marketplace.append(listing)
        self._log("list_trait", genome_id, price_nc, trait_name)
        return listing

    def list_memory(
        self, genome_id: str, memory_type: str, summary: str, price_nc: float,
    ) -> MemoryListing:
        listing = MemoryListing(genome_id, memory_type, summary, price_nc)
        self.memory_marketplace.append(listing)
        self._log("list_memory", genome_id, price_nc, memory_type)
        return listing

    def create_bounty(
        self,
        description: str,
        reward_nc: float,
        *,
        quantum_flag: bool = False,
        goal_id: str = "",
    ) -> Bounty:
        gid = goal_id or f"goal_{uuid.uuid4().hex[:8]}"
        bounty = Bounty(gid, description, reward_nc, quantum_flag=quantum_flag)
        self.bounties[gid] = bounty
        self._log("create_bounty", "OMNI_MIND", reward_nc, description[:80])
        return bounty

    def resolve_bounty(self, goal_id: str, assignees: list[str]) -> dict[str, Any]:
        bounty = self.bounties.get(goal_id)
        if not bounty or bounty.status != "open":
            return {"ok": False, "reason": "bounty unavailable"}
        share = bounty.reward_nc / max(len(assignees), 1)
        payouts: dict[str, float] = {}
        for agent in assignees:
            payouts[agent] = self.earn(agent, share, f"bounty {goal_id}")
        bounty.status = "resolved"
        bounty.assignees = assignees
        return {"ok": True, "goal_id": goal_id, "payouts": payouts}

    def soul_bond(self, agent_id: str, *, strength: float = 0.7) -> SoulBond:
        bond = SoulBond(agent_id, strength, time.time())
        self.soul_bonds[agent_id] = bond
        self._log("soul_bond", agent_id, strength, "alignment")
        return bond

    def maybe_soul_bond(self, agent_id: str, contribution_score: float) -> SoulBond | None:
        if contribution_score >= 0.8 and agent_id not in self.soul_bonds:
            return self.soul_bond(agent_id, strength=min(1.0, contribution_score))
        if agent_id in self.soul_bonds:
            bond = self.soul_bonds[agent_id]
            bond.strength = min(1.0, bond.strength + 0.02)
        return self.soul_bonds.get(agent_id)

    def snapshot(self) -> dict[str, Any]:
        return {
            "trait_listings": len(self.trait_marketplace),
            "memory_listings": len(self.memory_marketplace),
            "open_bounties": sum(1 for b in self.bounties.values() if b.status == "open"),
            "soul_bonds": len(self.soul_bonds),
            "transactions": len(self.transaction_history),
        }

    def _log(self, kind: str, agent: str, amount: float, detail: str) -> None:
        self.transaction_history.append({
            "kind": kind, "agent": agent,
            "amount": round(amount, 4), "detail": detail[:200],
            "ts": time.time(),
        })
        if len(self.transaction_history) > 500:
            self.transaction_history = self.transaction_history[-500:]


_engine: ValueFlowEngine | None = None


def get_value_flow() -> ValueFlowEngine:
    global _engine
    if _engine is None:
        _engine = ValueFlowEngine()
    return _engine