"""Multi-agent collaboration loop — five roles × six-step heartbeat economy."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from oss.kernel.agents import AgentRole, PERSONA_BRIDGE


class CollabStep(str, Enum):
    SCIENTIST_PROPOSE = "scientist_propose"
    BUILDER_DESIGN = "builder_design"
    OPERATOR_DEPLOY = "operator_deploy"
    INVESTOR_ALLOCATE = "investor_allocate"
    GOVERNOR_OVERSEE = "governor_oversee"
    TRAINING_FEEDBACK = "training_feedback"


@dataclass(frozen=True)
class Handoff:
    from_role: AgentRole
    to_roles: tuple[AgentRole, ...]
    artifact: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "from": self.from_role.value,
            "to": [r.value for r in self.to_roles],
            "artifact": self.artifact,
        }


@dataclass
class CollabStepResult:
    step: CollabStep
    agent: AgentRole
    persona: str
    inputs: list[str]
    outputs: list[str]
    handoffs: list[Handoff] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "step": self.step.value,
            "agent": self.agent.value,
            "persona": self.persona,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "handoffs": [h.to_dict() for h in self.handoffs],
        }


COLLAB_LOOP: tuple[CollabStep, ...] = (
    CollabStep.SCIENTIST_PROPOSE,
    CollabStep.BUILDER_DESIGN,
    CollabStep.OPERATOR_DEPLOY,
    CollabStep.INVESTOR_ALLOCATE,
    CollabStep.GOVERNOR_OVERSEE,
    CollabStep.TRAINING_FEEDBACK,
)

STEP_AGENT: dict[CollabStep, AgentRole] = {
    CollabStep.SCIENTIST_PROPOSE: AgentRole.SCIENTIST,
    CollabStep.BUILDER_DESIGN: AgentRole.BUILDER,
    CollabStep.OPERATOR_DEPLOY: AgentRole.OPERATOR,
    CollabStep.INVESTOR_ALLOCATE: AgentRole.INVESTOR,
    CollabStep.GOVERNOR_OVERSEE: AgentRole.GOVERNOR,
    CollabStep.TRAINING_FEEDBACK: AgentRole.GOVERNOR,
}


def _step_spec(step: CollabStep, ctx: dict[str, Any]) -> CollabStepResult:
    """Deterministic collaboration artifact for one step (dry-run safe)."""
    agent = STEP_AGENT[step]
    persona = PERSONA_BRIDGE.get(agent, "")
    domain = ctx.get("domain", "general")
    territory = ctx.get("territory", "unknown")
    revenue = ctx.get("revenue_nc", 0.0)
    tick = ctx.get("tick", 0)

    if step == CollabStep.SCIENTIST_PROPOSE:
        brief = (
            f"Research brief tick-{tick}: probe {territory} via {domain} — "
            "model phenomenon, predict impact, list applications"
        )
        return CollabStepResult(
            step=step, agent=agent, persona=persona,
            inputs=["theories", "simulation results", "predicted impacts"],
            outputs=[brief],
            handoffs=[
                Handoff(agent, (AgentRole.BUILDER, AgentRole.INVESTOR, AgentRole.GOVERNOR), brief),
            ],
        )

    if step == CollabStep.BUILDER_DESIGN:
        spec = f"Product spec: monetize {domain} insights from {territory} — UX flow + API surface"
        return CollabStepResult(
            step=step, agent=agent, persona=persona,
            inputs=["scientist brief", "market context", "governor constraints"],
            outputs=[spec, "monetization model", "API/service design"],
            handoffs=[
                Handoff(agent, (AgentRole.OPERATOR, AgentRole.INVESTOR), spec),
            ],
        )

    if step == CollabStep.OPERATOR_DEPLOY:
        deploy = f"Deployed service kernel-{tick}-{domain}: API + dashboard + logging pipeline"
        return CollabStepResult(
            step=step, agent=agent, persona=persona,
            inputs=["builder spec", "tooling options", "platform constraints"],
            outputs=[deploy, "monitoring pipeline"],
            handoffs=[
                Handoff(agent, (AgentRole.INVESTOR, AgentRole.GOVERNOR, AgentRole.BUILDER), deploy),
            ],
        )

    if step == CollabStep.INVESTOR_ALLOCATE:
        alloc = (
            f"Allocate {revenue:.1f} NC — back {domain} product, fund research on {territory}, "
            "size positions within risk buffer"
        )
        return CollabStepResult(
            step=step, agent=agent, persona=persona,
            inputs=["live metrics", "market/on-chain data", "governor risk limits"],
            outputs=[alloc, "portfolio allocation memo"],
            handoffs=[
                Handoff(agent, (AgentRole.OPERATOR, AgentRole.SCIENTIST, AgentRole.BUILDER), alloc),
            ],
        )

    if step == CollabStep.GOVERNOR_OVERSEE:
        ruling = "Approved with guardrails: no real funds, constitution preflight required"
        return CollabStepResult(
            step=step, agent=agent, persona=persona,
            inputs=["all proposals", "logs", "incidents", "outcomes"],
            outputs=[ruling, "updated guardrails"],
            handoffs=[
                Handoff(agent, tuple(AgentRole), ruling),
            ],
        )

    # TRAINING_FEEDBACK
    feedback = {
        "promote": [f"successful {domain} pattern"],
        "remediate": ["near-miss rule checks → new eval scenarios"],
        "new_shards": [f"{territory}_outcomes"],
    }
    return CollabStepResult(
        step=step, agent=agent, persona=persona,
        inputs=["decisions", "outcomes", "P&L", "incidents", "violations"],
        outputs=[
            f"promote: {feedback['promote']}",
            f"remediate: {feedback['remediate']}",
            f"new_shards: {feedback['new_shards']}",
        ],
        handoffs=[
            Handoff(agent, tuple(AgentRole), "curriculum update queued"),
        ],
    )


def run_collaboration_loop(
    *,
    tick: int,
    domain: str,
    territory: str,
    revenue_nc: float = 0.0,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Execute the six-step multi-agent interaction loop."""
    ctx = {
        "tick": tick,
        "domain": domain,
        "territory": territory,
        "revenue_nc": revenue_nc,
        "dry_run": dry_run,
    }
    steps = [_step_spec(s, ctx).to_dict() for s in COLLAB_LOOP]
    return {
        "tick": tick,
        "dry_run": dry_run,
        "loop": "scientist → builder → operator → investor → governor → training",
        "steps": steps,
        "closed_loop": "experience → data → curriculum → better agents → better decisions",
        "ts": time.time(),
    }


def collaboration_overview() -> dict[str, Any]:
    """Static description of the collaboration loop."""
    return {
        "steps": [
            {
                "order": 1,
                "step": CollabStep.SCIENTIST_PROPOSE.value,
                "agent": AgentRole.SCIENTIST.value,
                "summary": "Propose theories, models, research briefs",
                "handoff_to": ["builder", "investor", "governor"],
            },
            {
                "order": 2,
                "step": CollabStep.BUILDER_DESIGN.value,
                "agent": AgentRole.BUILDER.value,
                "summary": "Design products, UX, monetization from briefs",
                "handoff_to": ["operator", "investor"],
            },
            {
                "order": 3,
                "step": CollabStep.OPERATOR_DEPLOY.value,
                "agent": AgentRole.OPERATOR.value,
                "summary": "Build, deploy, monitor services",
                "handoff_to": ["investor", "governor", "builder"],
            },
            {
                "order": 4,
                "step": CollabStep.INVESTOR_ALLOCATE.value,
                "agent": AgentRole.INVESTOR.value,
                "summary": "Allocate capital across projects and strategies",
                "handoff_to": ["operator", "scientist", "builder"],
            },
            {
                "order": 5,
                "step": CollabStep.GOVERNOR_OVERSEE.value,
                "agent": AgentRole.GOVERNOR.value,
                "summary": "Approve, reject, update rules and guardrails",
                "handoff_to": ["all"],
            },
            {
                "order": 6,
                "step": CollabStep.TRAINING_FEEDBACK.value,
                "agent": "pipeline",
                "summary": "Promote successes, remediate failures, add shards",
                "handoff_to": ["curriculum"],
            },
        ],
        "feedback_logs": [
            "decisions", "outcomes", "profits/losses", "incidents",
            "user impacts", "rule violations", "near-misses",
        ],
    }


def ingest_tick_feedback(
    collab: dict[str, Any],
    *,
    violations: int = 0,
    near_misses: int = 0,
    revenue_nc: float = 0.0,
) -> dict[str, Any]:
    """Derive training pipeline actions from a collaboration cycle."""
    domain = collab.get("steps", [{}])[0].get("outputs", ["general"])[0][:80]
    promote: list[str] = []
    remediate: list[str] = []
    new_shards: list[str] = []

    if revenue_nc > 0:
        promote.append(f"revenue-positive pattern: {domain}")
    if violations > 0:
        remediate.append(f"{violations} rule violations → governor eval scenarios")
    if near_misses > 0:
        remediate.append(f"{near_misses} near-misses → safety shard updates")
    for step in collab.get("steps", []):
        if step.get("step") == CollabStep.TRAINING_FEEDBACK.value:
            for out in step.get("outputs", []):
                if out.startswith("new_shards:"):
                    new_shards.extend(out.replace("new_shards:", "").strip().strip("[]").split(","))

    return {
        "promote": promote or ["successful collaboration pattern"],
        "remediate": remediate or ["none this tick"],
        "new_shards": [s.strip() for s in new_shards if s.strip()],
        "pipeline": "experience → data → curriculum → better agents",
    }