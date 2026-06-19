"""
DEPRECATED - Legacy. Use backend/oss/omni_dna.py and MVS for all new code.
All improvements now live in the unified MVS (see omni_dna.py, genomic_substrate.py, mvs.py).
"""

from __future__ import annotations
import json
import random
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict

TRAIT_PATH = Path(__file__).resolve().parents[2] / "data" / "oss_traits.json"

DEFAULT_TRAITS = {
    "SCIENTIST": {"novelty_seeking": 0.75, "rigor": 0.82, "risk_tolerance": 0.45},
    "INVESTOR":  {"risk_tolerance": 0.55, "long_horizon": 0.78, "liquidity_preference": 0.65},
    "OPERATOR":  {"reliability": 0.88, "automation_bias": 0.60, "cost_sensitivity": 0.70},
    "GOVERNOR":  {"strictness": 0.72, "adaptiveness": 0.55, "transparency": 0.81},
    "BUILDER":   {"monetization_drive": 0.68, "user_empathy": 0.59, "speed": 0.74},
}

@dataclass
class TraitVector:
    role: str
    traits: Dict[str, float]

    def mutate(self, strength: float = 0.08):
        for k in self.traits:
            delta = random.gauss(0, strength)
            self.traits[k] = max(0.1, min(0.95, self.traits[k] + delta))

    def crossover(self, other: "TraitVector") -> "TraitVector":
        child = {}
        for k in self.traits:
            child[k] = (self.traits[k] + other.traits.get(k, self.traits[k])) / 2
        return TraitVector(role=f"{self.role}+{other.role}", traits=child)

def load_traits() -> Dict[str, TraitVector]:
    if TRAIT_PATH.exists():
        raw = json.loads(TRAIT_PATH.read_text())
        return {r: TraitVector(r, t) for r, t in raw.items()}
    return {r: TraitVector(r, t.copy()) for r, t in DEFAULT_TRAITS.items()}

def save_traits(traits: Dict[str, TraitVector]):
    TRAIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = {r: tv.traits for r, tv in traits.items()}
    TRAIT_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")

def evolve_from_rewards(rewards: dict, traits: Dict[str, TraitVector]) -> Dict[str, float]:
    """Apply differential evolution: high-reward roles mutate toward success, low ones explore."""
    fitness = {}
    for role, tv in traits.items():
        r = rewards.get(role.lower(), 0.55)
        fitness[role] = r
        if r > 0.72:
            tv.mutate(0.03)   # small refinement
        elif r < 0.48:
            tv.mutate(0.12)   # stronger exploration
    save_traits(traits)
    return fitness

if __name__ == "__main__":
    t = load_traits()
    print("Current traits:", {r: tv.traits for r, tv in t.items()})
    # simulate one evolution step
    dummy_rewards = {"scientist": 0.61, "investor": 0.48, "operator": 0.71, "governor": 0.68, "builder": 0.55}
    evolve_from_rewards(dummy_rewards, t)
    print("After evolution step:", {r: tv.traits for r, tv in t.items()})
