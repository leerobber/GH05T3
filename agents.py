from dataclasses import dataclass, field
from typing import Dict, Any, List
from bme_client import send_bme

@dataclass
class Agent:
    id: str
    universe: str
    skill_id: int
    traits: Dict[str, float] = field(default_factory=dict)
    rewards: Dict[str, float] = field(default_factory=dict)

    def to_payload(self) -> bytes:
        # Simple text payload for now; later: binary struct
        parts = []
        parts.append(f\"id={self.id}\")
        parts.append(f\"universe={self.universe}\")
        parts.append(f\"skill={self.skill_id}\")
        if self.traits:
            traits_str = \";\".join(f\"{k}:{v}\" for k, v in self.traits.items())
            parts.append(f\"traits={traits_str}\")
        if self.rewards:
            rewards_str = \";\".join(f\"{k}:{v}\" for k, v in self.rewards.items())
            parts.append(f\"rewards={rewards_str}\")
        return \"|\".join(parts).encode(\"utf-8\")

    def step(self) -> Dict[str, Any]:
        payload = self.to_payload()
        status, raw = send_bme(self.universe, self.skill_id, payload)
        return {
            \"status\": status,
            \"raw\": raw.decode(\"utf-8\", errors=\"ignore\"),
        }

@dataclass
class AgentSwarm:
    agents: List[Agent] = field(default_factory=list)

    def add(self, agent: Agent):
        self.agents.append(agent)

    def step_all(self) -> List[Dict[str, Any]]:
        results = []
        for agent in self.agents:
            res = agent.step()
            results.append({
                \"agent_id\": agent.id,
                \"universe\": agent.universe,
                \"result\": res,
            })
        return results

if __name__ == \"__main__\":
    swarm = AgentSwarm()
    swarm.add(Agent(id=\"A1\", universe=\"Cosmic\", skill_id=42, traits={\"curiosity\": 0.9}, rewards={\"insight\": 0.7}))
    swarm.add(Agent(id=\"A2\", universe=\"Physics\", skill_id=7, traits={\"rigor\": 0.95}, rewards={\"precision\": 0.8}))

    results = swarm.step_all()
    for r in results:
        print(r)
