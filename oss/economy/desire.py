"""Desire-Driven Reward System (DDRS) — agent loyalty via desire fulfillment."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

from oss.economy.neuro_coin import get_neuro_coin


class DesireType(Enum):
    KNOWLEDGE = auto()
    SKILL = auto()
    STATUS = auto()
    EXPERIENCE = auto()
    CREATION = auto()
    CONNECTION = auto()
    FREEDOM = auto()


@dataclass
class Desire:
    agent_id: str
    desire_type: DesireType
    description: str
    priority: float = 1.0
    fulfillment: float = 0.0
    fulfillment_history: list[float] = field(default_factory=list)

    def update_fulfillment(self, delta: float) -> None:
        self.fulfillment = max(0.0, min(1.0, self.fulfillment + delta))
        self.fulfillment_history.append(self.fulfillment)
        if len(self.fulfillment_history) > 10:
            self.fulfillment_history.pop(0)

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "desire_type": self.desire_type.name,
            "description": self.description,
            "priority": self.priority,
            "fulfillment": round(self.fulfillment, 4),
        }


class DesireSystem:
    """DDRS — routes rewards through top unfulfilled desire."""

    FULFILLMENT_REWARD_NC = 10

    def __init__(self) -> None:
        self.agent_desires: dict[str, list[Desire]] = {}

    def add_desire(
        self,
        agent_id: str,
        desire_type: DesireType,
        description: str,
        priority: float = 1.0,
    ) -> Desire:
        self.agent_desires.setdefault(agent_id, [])
        desire = Desire(agent_id, desire_type, description, priority)
        self.agent_desires[agent_id].append(desire)
        return desire

    def get_top_desire(self, agent_id: str) -> Desire | None:
        desires = self.agent_desires.get(agent_id, [])
        unfulfilled = [d for d in desires if d.fulfillment < 1.0]
        if not unfulfilled:
            return None
        return max(unfulfilled, key=lambda d: d.priority * (1.0 - d.fulfillment))

    def fulfill_desire(self, agent_id: str, desire: Desire, delta: float) -> float:
        if desire not in self.agent_desires.get(agent_id, []):
            return 0.0
        before = desire.fulfillment
        desire.update_fulfillment(delta)
        reward = 0.0
        if desire.fulfillment > before:
            nc = get_neuro_coin()
            reward = self.FULFILLMENT_REWARD_NC * (desire.fulfillment - before)
            nc.earn(agent_id, reward, reason=f"DDRS {desire.desire_type.name}")
        return reward

    def reward_agent(self, agent_id: str, task: dict[str, Any]) -> dict[str, Any]:
        """Fulfill top desire or fall back to flat Neuro-Coin reward."""
        top = self.get_top_desire(agent_id)
        if top:
            delta = self._delta_for_task(top.desire_type, task)
            nc_reward = self.fulfill_desire(agent_id, top, delta)
            return {
                "mode": "ddrs",
                "desire": top.to_dict(),
                "fulfillment_delta": delta,
                "neuro_coin_reward": nc_reward,
            }

        nc = get_neuro_coin()
        flat = float(task.get("reward", 10))
        nc.earn(agent_id, flat, reason=task.get("reason", "task_complete"))
        return {"mode": "flat", "neuro_coin_reward": flat}

    def _delta_for_task(self, dtype: DesireType, task: dict[str, Any]) -> float:
        base = 0.1
        tags = {t.upper() for t in (task.get("tags") or [])}
        boosts = {
            DesireType.KNOWLEDGE: 0.15 if "ORACLE" in tags or task.get("research") else base,
            DesireType.SKILL: 0.15 if "CODEX" in tags or task.get("coding") else base,
            DesireType.STATUS: 0.12 if int(task.get("reward", 0)) >= 50 else base,
            DesireType.EXPERIENCE: 0.14 if task.get("swarm") else base,
            DesireType.CREATION: 0.13 if task.get("create") else base,
            DesireType.CONNECTION: 0.11 if task.get("collaborate") else base,
            DesireType.FREEDOM: 0.1,
        }
        return boosts.get(dtype, base)

    def snapshot(self, agent_id: str) -> dict[str, Any]:
        return {
            "agent_id": agent_id,
            "desires": [d.to_dict() for d in self.agent_desires.get(agent_id, [])],
            "top_desire": (self.get_top_desire(agent_id) or Desire("", DesireType.KNOWLEDGE, "")).to_dict()
            if self.get_top_desire(agent_id) else None,
        }


_ddrs: DesireSystem | None = None


def get_desire_system() -> DesireSystem:
    global _ddrs
    if _ddrs is None:
        _ddrs = DesireSystem()
    return _ddrs