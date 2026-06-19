"""InteractionField — publish intents instead of fixed API calls."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Intent:
    """Published into a field — agents respond with offers, not HTTP 200."""

    intent_id: str
    field: str
    publisher: str
    payload: dict[str, Any]
    ts: float = field(default_factory=time.time)
    responses: list[dict[str, Any]] = field(default_factory=list)
    consensus: dict[str, Any] | None = None
    status: str = "open"

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent_id": self.intent_id,
            "field": self.field,
            "publisher": self.publisher,
            "payload": self.payload,
            "ts": self.ts,
            "responses": self.responses,
            "consensus": self.consensus,
            "status": self.status,
        }


class InteractionField:
    """
    Shared negotiation space — replaces POST /predict style APIs.

    Agents publish intents; capable genomes respond with confidence/cost/risk.
    """

    FIELDS = frozenset({
        "prediction", "research", "deployment", "allocation",
        "governance", "product_design", "swarm_solve",
    })

    def __init__(self) -> None:
        self._intents: dict[str, Intent] = {}

    def publish_intent(
        self,
        field: str,
        agent: str,
        payload: dict[str, Any],
    ) -> Intent:
        if field not in self.FIELDS:
            field = "swarm_solve"
        intent = Intent(
            intent_id=f"intent_{uuid.uuid4().hex[:10]}",
            field=field,
            publisher=agent,
            payload=payload,
        )
        self._intents[intent.intent_id] = intent
        return intent

    def respond(
        self,
        intent_id: str,
        *,
        agent: str,
        offer: str,
        confidence: float = 0.7,
        cost_nc: float = 0.0,
        risk: float = 0.1,
    ) -> dict[str, Any]:
        intent = self._intents.get(intent_id)
        if not intent or intent.status != "open":
            return {"ok": False, "reason": "intent closed or missing"}
        resp = {
            "agent": agent,
            "offer": offer[:500],
            "confidence": round(confidence, 4),
            "cost_nc": cost_nc,
            "risk": round(risk, 4),
            "ts": time.time(),
        }
        intent.responses.append(resp)
        return {"ok": True, "response": resp}

    def collect_responses(self, intent_id: str) -> list[dict[str, Any]]:
        intent = self._intents.get(intent_id)
        return intent.responses if intent else []

    def reach_consensus(self, intent_id: str) -> dict[str, Any]:
        intent = self._intents.get(intent_id)
        if not intent or not intent.responses:
            intent = intent or Intent(intent_id, "unknown", "", {})
            intent.consensus = {"winner": None, "score": 0.0}
            intent.status = "no_responses"
            return intent.consensus

        best = max(
            intent.responses,
            key=lambda r: r["confidence"] - r["risk"] - r["cost_nc"] * 0.01,
        )
        intent.consensus = {
            "winner": best["agent"],
            "offer": best["offer"],
            "score": round(best["confidence"] - best["risk"], 4),
        }
        intent.status = "consensus"
        return intent.consensus

    def form_swarm(self, intent_id: str, *, min_confidence: float = 0.5) -> list[str]:
        intent = self._intents.get(intent_id)
        if not intent:
            return []
        return [
            r["agent"] for r in intent.responses
            if r["confidence"] >= min_confidence
        ]

    def list_open(self, field: str | None = None) -> list[dict[str, Any]]:
        out = []
        for intent in self._intents.values():
            if intent.status == "open":
                if field is None or intent.field == field:
                    out.append(intent.to_dict())
        return out


_field: InteractionField | None = None


def get_interaction_field() -> InteractionField:
    global _field
    if _field is None:
        _field = InteractionField()
    return _field