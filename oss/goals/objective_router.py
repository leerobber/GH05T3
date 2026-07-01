"""
ObjectiveRouter — maps high-level goals into concrete evolution objectives.

Objectives drive how MetaScheduler steers LivingLoop cycles.
"""
from __future__ import annotations

from dataclasses import dataclass


VALID_OBJECTIVES = frozenset({"stability", "sharpness", "exploration", "exploitation"})


@dataclass
class ObjectiveState:
    current: str = "stability"


class ObjectiveRouter:
    """
    Routes high-level goals into one of four concrete objectives:
      "stability"    — prefer low entropy, controlled growth
      "sharpness"    — maximise attention focus / low-entropy heads
      "exploration"  — wide mutation, novel genome discovery
      "exploitation" — fine-tune around best known genome
    """

    def __init__(self) -> None:
        self.state = ObjectiveState()

    def set_objective(self, objective: str) -> None:
        if objective not in VALID_OBJECTIVES:
            raise ValueError(f"Unknown objective '{objective}'; valid: {sorted(VALID_OBJECTIVES)}")
        self.state.current = objective

    def get_objective(self) -> str:
        return self.state.current
