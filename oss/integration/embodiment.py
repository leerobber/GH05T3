"""AgentEmbodiment — DNA + role + perceive/act/evolve."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from oss.dna.omni_dna import OmniDNA
from oss.substrate.species_registry import SpeciesRole, get_species_registry


@dataclass
class AgentEmbodiment:
    """One living agent — genome segment activated in a species role."""

    dna: OmniDNA
    role: SpeciesRole
    context: dict[str, Any] = field(default_factory=dict)

    @property
    def agent_id(self) -> str:
        return self.dna.registry_agent_id

    @property
    def genome_id(self) -> str:
        return self.dna.genome_id

    def perceive(self, event: dict[str, Any]) -> None:
        self.dna.add_memory({
            "type": "perception",
            "role": self.role.name,
            "event": event.get("kind", "observation"),
            "domain": event.get("domain", ""),
            "metrics": event.get("metrics", {}),
        })
        if event.get("success"):
            self.dna.qualia["joy"] = min(1.0, self.dna.qualia.get("joy", 0) + 0.05)
            self.dna.qualia["curiosity"] = min(1.0, self.dna.qualia.get("curiosity", 0.5) + 0.03)
        elif event.get("failure"):
            self.dna.qualia["frustration"] = min(1.0, self.dna.qualia.get("frustration", 0) + 0.05)

    def act(self, intent: dict[str, Any]) -> dict[str, Any]:
        action = intent.get("action", "propose")
        artifact = (
            f"[{self.role.persona}/{self.role.name}] {action}: "
            f"{intent.get('summary', intent.get('domain', 'task'))}"
        )
        self.dna.add_memory({
            "type": "action",
            "action": action,
            "artifact": artifact[:300],
            "role": self.role.name,
        })
        return {
            "agent_id": self.agent_id,
            "genome_id": self.genome_id,
            "role": self.role.name,
            "artifact": artifact,
            "action": action,
        }

    def evolve(self, score: float) -> dict[str, float]:
        deltas = self.dna.evolve(score=score)
        self.dna.meta_dna["last_fitness"] = score
        return deltas


def embody_role(role_name: str) -> AgentEmbodiment | None:
    registry = get_species_registry()
    schema = registry.get_role(role_name)
    if not schema:
        return None
    from oss.mind.omni_mind import get_mind
    mind = get_mind()
    if not mind.agents:
        mind.bootstrap()
    persona = schema.persona
    dna = next(
        (d for d in mind.agents.values() if d.registry_agent_id == persona),
        registry.spawn(role_name),
    )
    return AgentEmbodiment(dna=dna, role=schema)