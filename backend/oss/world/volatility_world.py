# backend/oss/world/volatility_world.py

from typing import Dict, Any
import random
import math


class VolatilityWorld:
    """
    Simple synthetic environment:
    - generates regime-switching volatility time series
    - evaluates proposed models against data
    """

    def __init__(self, length: int = 500):
        self.length = length

    def generate_series(self) -> Dict[str, Any]:
        regimes = [0.1, 0.3, 0.6]
        series = []
        current = random.choice(regimes)
        for _ in range(self.length):
            if random.random() < 0.05:
                current = random.choice(regimes)
            series.append(abs(random.gauss(0, current)))
        return {"series": series, "regimes": regimes}

    def evaluate_model(self, model_text: str, data: Dict[str, Any]) -> float:
        # Very rough heuristic: reward mention of regimes, volatility, switching
        score = 0.0
        t = model_text.lower()
        if "regime" in t:
            score += 0.3
        if "volatility" in t:
            score += 0.3
        if "switch" in t or "transition" in t:
            score += 0.2
        # small bonus for math-y language
        if "distribution" in t or "stochastic" in t or "process" in t:
            score += 0.2
        return min(score, 1.0)
