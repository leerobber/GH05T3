from __future__ import annotations

import random

from oss.dna.omni_dna import OmniDNA


def select_agents_for_task(
    agents: dict[str, OmniDNA],
    required_traits: list[str],
    max_agents: int = 5,
    threshold: float = 0.5,
) -> list[str]:
    """Trait-gated probabilistic agent selection."""
    selected: list[str] = []
    for genome_id, dna in agents.items():
        has_traits = all(dna.trait_value(t) >= threshold for t in required_traits)
        if has_traits and random.random() < 0.7:
            selected.append(genome_id)
    if not selected and agents:
        # Fallback: top trait match
        ranked = sorted(
            agents.items(),
            key=lambda kv: sum(kv[1].trait_value(t) for t in required_traits),
            reverse=True,
        )
        selected = [ranked[0][0]]
    return selected[:max_agents]