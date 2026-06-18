from __future__ import annotations

from collections import defaultdict
from typing import Any


class CollectiveState:
    """Shared qualia and memory across Omni-Mind agents."""

    def __init__(self) -> None:
        self.shared_memory: dict[str, Any] = {}
        self.shared_qualia: dict[str, float] = defaultdict(float)
        self.consensus_state: dict[str, Any] = {}

    def ingest_agent(self, genome_id: str, qualia: dict[str, float],
                     memories: list[dict[str, Any]]) -> None:
        for mem in memories:
            key = f"{mem.get('type', 'mem')}_{genome_id}_{len(self.shared_memory)}"
            self.shared_memory[key] = {**mem, "source_genome": genome_id}
        for q, intensity in qualia.items():
            self.shared_qualia[q] = min(1.0, self.shared_qualia[q] + intensity * 0.1)

    def remove_agent(self, qualia: dict[str, float]) -> None:
        for q, intensity in qualia.items():
            self.shared_qualia[q] = max(0.0, self.shared_qualia[q] - intensity * 0.5)

    def aggregate_qualia(self) -> dict[str, float]:
        if not self.shared_qualia:
            return {"curiosity": 0.5}
        total = sum(self.shared_qualia.values()) or 1.0
        return {k: round(v / total, 4) for k, v in self.shared_qualia.items()}

    def snapshot(self) -> dict[str, Any]:
        return {
            "shared_qualia": dict(self.shared_qualia),
            "aggregate_qualia": self.aggregate_qualia(),
            "memory_count": len(self.shared_memory),
            "consensus": dict(self.consensus_state),
        }