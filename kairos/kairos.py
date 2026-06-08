"""
KAIROS — 6-Phase Deterministic State Machine
=============================================
Phases:
  K — Kickoff   : Goal initialisation, context loading
  A — Align     : Intent verification, sovereign parameter check
  I — Implement : Logic execution, code generation
  R — Refine    : Delta analysis, self-critique
  O — Optimize  : Performance tuning, throughput maximisation
  S — Scale     : Swarm propagation, deployment

Each phase calls the appropriate agent via Ollama and produces a structured
KAIROSPlan that drives the SAGE self-improvement loop.

Usage:
    engine = KAIROSEngine()
    plan = await engine.run("Build a 90-day GTM plan for Aethyro CPA vertical")
    print(plan.to_markdown())
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Coroutine, Dict, List, Optional

import httpx

LOG = logging.getLogger("aethyro.kairos")

_OLLAMA_URL  = "http://localhost:11434/api/generate"
_RULES_PATH  = Path(__file__).parent / "data" / "improvement_rules.json"
_PLANS_PATH  = Path(__file__).parent / "data" / "kairos_plans.json"


# ─────────────────────────────────────────────────────────────────────────────
# Default improvement rules (written by Meta-Agent)
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_RULES: Dict = {
    "version": 1,
    "meta_cycles": 0,
    "rules": [
        {
            "id": "R001",
            "phase": "Kickoff",
            "directive": "Always define a single, measurable success metric for the goal.",
            "weight": 1.0,
        },
        {
            "id": "R002",
            "phase": "Align",
            "directive": "Verify the goal does not require external cloud API calls or data egress.",
            "weight": 1.0,
        },
        {
            "id": "R003",
            "phase": "Implement",
            "directive": "Prefer Python async over synchronous code for all I/O operations.",
            "weight": 0.9,
        },
        {
            "id": "R004",
            "phase": "Refine",
            "directive": "Always include at least one failure mode and its mitigation.",
            "weight": 0.9,
        },
        {
            "id": "R005",
            "phase": "Optimize",
            "directive": "Target sub-100ms latency for all agent responses under normal load.",
            "weight": 0.8,
        },
        {
            "id": "R006",
            "phase": "Scale",
            "directive": "Any new logic must be backward-compatible with existing swarm bus contracts.",
            "weight": 1.0,
        },
    ],
    "updated_at": time.time(),
}


def _load_rules() -> Dict:
    _RULES_PATH.parent.mkdir(parents=True, exist_ok=True)
    if _RULES_PATH.exists():
        try:
            return json.loads(_RULES_PATH.read_text())
        except Exception:
            pass
    _RULES_PATH.write_text(json.dumps(DEFAULT_RULES, indent=2))
    return DEFAULT_RULES


def _save_rules(rules: Dict) -> None:
    _RULES_PATH.parent.mkdir(parents=True, exist_ok=True)
    _RULES_PATH.write_text(json.dumps(rules, indent=2))


# ─────────────────────────────────────────────────────────────────────────────
# Data structures
# ─────────────────────────────────────────────────────────────────────────────

class KAIROSPhase(str, Enum):
    KICKOFF   = "Kickoff"
    ALIGN     = "Align"
    IMPLEMENT = "Implement"
    REFINE    = "Refine"
    OPTIMIZE  = "Optimize"
    SCALE     = "Scale"


@dataclass
class PhaseResult:
    phase:      KAIROSPhase
    agent:      str
    output:     str
    actions:    List[str]         = field(default_factory=list)
    success_metric: Optional[str] = None
    issues:     List[str]         = field(default_factory=list)
    latency_ms: float             = 0.0
    ts:         float             = field(default_factory=time.time)


@dataclass
class KAIROSPlan:
    plan_id:   str                  = field(default_factory=lambda: str(uuid.uuid4())[:12])
    goal:      str                  = ""
    phases:    List[PhaseResult]    = field(default_factory=list)
    score:     float                = 0.0
    passed:    bool                 = False
    created_at: float               = field(default_factory=time.time)
    meta:      Dict[str, Any]       = field(default_factory=dict)

    def to_dict(self) -> Dict:
        d = asdict(self)
        d["phases"] = [
            {**asdict(p), "phase": p["phase"]} for p in d["phases"]
        ]
        return d

    def to_markdown(self) -> str:
        lines = [
            f"# KAIROS Plan — {self.plan_id}",
            f"**Goal:** {self.goal}",
            f"**Score:** {self.score:.2f}  |  **Passed:** {self.passed}",
            "",
        ]
        for pr in self.phases:
            lines += [
                f"## {pr.phase.value if hasattr(pr.phase, 'value') else pr.phase}  `[{pr.agent}]`",
                pr.output[:600],
                "",
            ]
            if pr.actions:
                lines += ["**Actions:**"] + [f"- {a}" for a in pr.actions] + [""]
            if pr.issues:
                lines += ["**Issues:**"] + [f"- {i}" for i in pr.issues] + [""]
        return "\n".join(lines)

    def save(self) -> None:
        """Append this plan to the plans archive."""
        _PLANS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_PLANS_PATH, "a") as f:
            f.write(json.dumps(self.to_dict()) + "\n")


# ─────────────────────────────────────────────────────────────────────────────
# Ollama call helper
# ─────────────────────────────────────────────────────────────────────────────

PHASE_AGENTS = {
    KAIROSPhase.KICKOFF:   "avery-sovereign",
    KAIROSPhase.ALIGN:     "avery-sovereign",
    KAIROSPhase.IMPLEMENT: "forge-sovereign",
    KAIROSPhase.REFINE:    "oracle-sovereign",
    KAIROSPhase.OPTIMIZE:  "nexus-sovereign",
    KAIROSPhase.SCALE:     "nexus-sovereign",
}

FALLBACK_MODEL = "avery-sovereign"


async def _llm_call(model: str, prompt: str, timeout: float = 60.0) -> str:
    """Make a single Ollama inference call. Returns generated text."""
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.3, "num_predict": 512},
    }
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            r = await client.post(_OLLAMA_URL, json=payload)
            if r.status_code == 200:
                return r.json().get("response", "").strip()
        except httpx.TimeoutException:
            LOG.warning("[KAIROS] Ollama timeout for model=%s", model)
        except Exception as e:
            LOG.warning("[KAIROS] Ollama error: %s", e)

        # Fallback to avery-sovereign if primary fails
        if model != FALLBACK_MODEL:
            try:
                payload["model"] = FALLBACK_MODEL
                r = await client.post(_OLLAMA_URL, json=payload)
                if r.status_code == 200:
                    return r.json().get("response", "").strip()
            except Exception:
                pass
    return f"[{model}] response unavailable"


# ─────────────────────────────────────────────────────────────────────────────
# KAIROS Engine
# ─────────────────────────────────────────────────────────────────────────────

class KAIROSEngine:
    """
    Drives a goal through all 6 KAIROS phases and returns a KAIROSPlan.
    Reads/writes improvement rules from kairos/data/improvement_rules.json.
    """

    def __init__(self):
        self.rules = _load_rules()

    def reload_rules(self) -> None:
        """Reload improvement rules from disk (called after Meta-Agent update)."""
        self.rules = _load_rules()
        LOG.info("[KAIROS] Rules reloaded — version %d", self.rules.get("version", 0))

    def _rules_for_phase(self, phase: KAIROSPhase) -> List[Dict]:
        return [
            r for r in self.rules.get("rules", [])
            if r.get("phase") in (phase.value, "All")
        ]

    def _build_phase_prompt(
        self,
        phase: KAIROSPhase,
        goal: str,
        previous_outputs: List[str],
        context: str = "",
    ) -> str:
        phase_rules = self._rules_for_phase(phase)
        rules_block = "\n".join(
            f"- [{r['id']}] {r['directive']}" for r in phase_rules
        ) or "No specific rules — use best judgement."

        prev_block = ""
        if previous_outputs:
            prev_block = "\n\nPrevious phase outputs:\n" + "\n---\n".join(
                f"[Phase {i+1}] {o[:400]}" for i, o in enumerate(previous_outputs)
            )

        phase_descs = {
            KAIROSPhase.KICKOFF:   "Define the goal scope, key stakeholders, resources required, and the ONE metric that proves success.",
            KAIROSPhase.ALIGN:     "Verify the goal aligns with sovereign parameters (zero-egress, local inference, privacy). Identify any conflicts.",
            KAIROSPhase.IMPLEMENT: "Write the concrete implementation steps. If code is needed, produce it. Be specific and actionable.",
            KAIROSPhase.REFINE:    "Critique the previous phases. Identify logical contradictions, failure modes, and their mitigations.",
            KAIROSPhase.OPTIMIZE:  "Identify the highest-leverage optimisation. Reduce overhead. Maximise throughput. Cut anything redundant.",
            KAIROSPhase.SCALE:     "Define how to propagate this across the swarm. What changes need to be deployed? In what order?",
        }

        return f"""You are the Aethyro sovereign AI system executing the KAIROS framework.

## Current Phase: {phase.value}
## Objective: {phase_descs.get(phase, '')}

## Goal
{goal}

## Improvement Rules for this Phase
{rules_block}
{prev_block}
{('## Additional Context\n' + context) if context else ''}

Respond with:
1. A concise output for this phase (3-5 sentences or bullet points)
2. ACTIONS: 2-3 specific next actions (prefix each with "ACTION: ")
3. METRIC: The one success metric for this phase (prefix with "METRIC: ")
4. ISSUES: Any issues found (prefix each with "ISSUE: ")

Be direct. No preamble. No markdown headers."""

    async def run(
        self,
        goal: str,
        context: str = "",
        phase_hooks: Optional[Dict[KAIROSPhase, Callable[..., Coroutine]]] = None,
    ) -> KAIROSPlan:
        """
        Execute all 6 KAIROS phases and return a KAIROSPlan.

        Args:
            goal:        The strategic objective to plan
            context:     Optional additional context (injected into each phase)
            phase_hooks: Optional async callbacks called after each phase
        """
        LOG.info("[KAIROS] Starting plan for goal: %s", goal[:80])
        plan = KAIROSPlan(goal=goal)
        previous_outputs: List[str] = []

        phases = [
            KAIROSPhase.KICKOFF,
            KAIROSPhase.ALIGN,
            KAIROSPhase.IMPLEMENT,
            KAIROSPhase.REFINE,
            KAIROSPhase.OPTIMIZE,
            KAIROSPhase.SCALE,
        ]

        for phase in phases:
            agent  = PHASE_AGENTS[phase]
            prompt = self._build_phase_prompt(phase, goal, previous_outputs, context)
            t0     = time.time()
            raw    = await _llm_call(agent, prompt, timeout=90.0)
            latency = (time.time() - t0) * 1000

            # Parse structured output
            output  = []
            actions = []
            metric  = None
            issues  = []

            for line in raw.splitlines():
                ls = line.strip()
                if ls.startswith("ACTION:"):
                    actions.append(ls[7:].strip())
                elif ls.startswith("METRIC:"):
                    metric = ls[7:].strip()
                elif ls.startswith("ISSUE:"):
                    issues.append(ls[6:].strip())
                else:
                    output.append(ls)

            output_text = "\n".join(filter(None, output)).strip() or raw[:500]

            pr = PhaseResult(
                phase=phase,
                agent=agent,
                output=output_text,
                actions=actions or ["Review output and proceed to next phase."],
                success_metric=metric,
                issues=issues,
                latency_ms=round(latency, 1),
            )
            plan.phases.append(pr)
            previous_outputs.append(output_text)

            LOG.info("[KAIROS] Phase %s done (%.0fms) — %d actions, %d issues",
                     phase.value, latency, len(actions), len(issues))

            # Run phase hook if provided
            if phase_hooks and phase in phase_hooks:
                try:
                    await phase_hooks[phase](pr)
                except Exception as e:
                    LOG.warning("[KAIROS] Phase hook error: %s", e)

        # Compute plan score
        total_issues  = sum(len(p.issues) for p in plan.phases)
        total_actions = sum(len(p.actions) for p in plan.phases)
        issue_penalty = min(0.3, total_issues * 0.05)
        plan.score    = round(max(0.0, 0.75 + (total_actions * 0.01) - issue_penalty), 3)
        plan.passed   = plan.score >= 0.75

        # Log to Iron Dome
        try:
            from memory.iron_dome import dome_write
            dome_write("KAIROSEngine", "plan_completed", {
                "plan_id": plan.plan_id,
                "score": plan.score,
                "passed": plan.passed,
                "phases": len(plan.phases),
            })
        except Exception:
            pass

        plan.save()
        LOG.info("[KAIROS] Plan %s complete — score=%.3f passed=%s",
                 plan.plan_id, plan.score, plan.passed)
        return plan

    async def quick_plan(self, goal: str, phases: Optional[List[KAIROSPhase]] = None) -> KAIROSPlan:
        """Run only specific KAIROS phases (faster, for simple tasks)."""
        phases_to_run = phases or [KAIROSPhase.KICKOFF, KAIROSPhase.IMPLEMENT, KAIROSPhase.SCALE]
        full_phases = [
            KAIROSPhase.KICKOFF,
            KAIROSPhase.ALIGN,
            KAIROSPhase.IMPLEMENT,
            KAIROSPhase.REFINE,
            KAIROSPhase.OPTIMIZE,
            KAIROSPhase.SCALE,
        ]
        plan = KAIROSPlan(goal=goal, meta={"quick": True, "phases_run": [p.value for p in phases_to_run]})
        previous_outputs: List[str] = []

        for phase in full_phases:
            if phase not in phases_to_run:
                continue
            agent  = PHASE_AGENTS[phase]
            prompt = self._build_phase_prompt(phase, goal, previous_outputs)
            raw    = await _llm_call(agent, prompt, timeout=60.0)
            actions = [l[7:].strip() for l in raw.splitlines() if l.strip().startswith("ACTION:")]
            pr = PhaseResult(phase=phase, agent=agent, output=raw[:600], actions=actions)
            plan.phases.append(pr)
            previous_outputs.append(raw[:400])

        plan.score  = 0.70
        plan.passed = False  # quick plans don't auto-pass verification
        return plan

    @staticmethod
    def load_plans(limit: int = 20) -> List[Dict]:
        """Return the N most recent KAIROS plans."""
        if not _PLANS_PATH.exists():
            return []
        lines = _PLANS_PATH.read_text().strip().splitlines()
        plans = []
        for line in reversed(lines[-limit:]):
            try:
                plans.append(json.loads(line))
            except Exception:
                pass
        return plans
