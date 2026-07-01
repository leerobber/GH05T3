"""
NarrativeTrace — structured event log for governance decisions.

Records why SentinelPrime and DeployManager made deployment decisions,
enabling long-horizon introspection without external logging services.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class TraceEvent:
    epoch: int
    action: str
    genome_id: str | None
    details: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "epoch": self.epoch,
            "action": self.action,
            "genome_id": self.genome_id,
            "details": self.details,
        }


class NarrativeTrace:
    """
    Records governance actions (promotions, retirements, objective shifts)
    with epoch context so decisions can be replayed or audited.
    """

    def __init__(self) -> None:
        self.events: List[TraceEvent] = []
        self._epoch: int = 0

    def next_epoch(self) -> None:
        self._epoch += 1

    def log(self, action: str, genome_id: str | None = None, **details: Any) -> None:
        self.events.append(
            TraceEvent(
                epoch=self._epoch,
                action=action,
                genome_id=genome_id,
                details=details,
            )
        )

    def filter(self, *, action: str | None = None, genome_id: str | None = None) -> List[TraceEvent]:
        """Return events matching optional action and/or genome_id filters."""
        result = self.events
        if action is not None:
            result = [e for e in result if e.action == action]
        if genome_id is not None:
            result = [e for e in result if e.genome_id == genome_id]
        return result

    def to_dict(self) -> Dict[str, Any]:
        return {"events": [e.to_dict() for e in self.events]}
