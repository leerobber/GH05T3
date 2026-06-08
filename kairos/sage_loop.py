"""
SAGE — Self-Improvement Engine
===============================
Nightly self-improvement loop that runs at 3:00 AM local time.

Algorithm per cycle:
  1. STATE ASSESSMENT  — Detect inefficiencies via Iron Dome + memory stats
  2. STRATEGIC MAPPING — Avery drafts a KAIROS optimisation plan
  3. PARALLEL PROPOSE  — 7 specialist agents generate improvement proposals
  4. GROUP EVOLUTION   — Proposals are peer-reviewed (adversarial critique)
  5. VERIFICATION GATE — 3-gate pipeline: Ethics + Sim + CLARA (score >= 0.85)
  6. SWARM PROPAGATION — Nexus deploys approved changes via GitOpsMutator
  7. META-AGENT        — Every 3 cycles, Meta-Agent rewrites improvement rules

10 cycles run per nightly session. Results are stored in Iron Dome.

API:
  GET /sage/status    — current cycle, last run, schedule
  POST /sage/run      — trigger a manual run (1 cycle)
  GET /sage/history   — last 20 cycle reports
  WebSocket /sage/ws  — real-time cycle events (for Honcho dashboard)

Usage:
    engine = SAGELoop()
    await engine.run_cycle()            # single cycle
    await run_sage_loop_service()       # start full nightly scheduler
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Coroutine, Dict, List, Optional

import httpx

from .kairos        import KAIROSEngine, KAIROSPhase
from .verification  import VerificationPipeline
from .meta_agent    import MetaAgent
from .gitops_mutator import GitOpsMutator

LOG = logging.getLogger("aethyro.sage")

_OLLAMA_URL  = "http://localhost:11434/api/generate"
_DATA_DIR    = Path(__file__).parent / "data"
_HISTORY_PATH = _DATA_DIR / "sage_history.jsonl"

CYCLES_PER_SESSION   = 10
PROPOSERS_PER_CYCLE  = 7
NIGHTLY_HOUR         = 3    # 3:00 AM
NIGHTLY_MINUTE       = 0

# Agents used for proposal generation
PROPOSER_AGENTS = [
    "avery-sovereign",
    "forge-sovereign",
    "oracle-sovereign",
    "sentinel-sovereign",
    "nexus-sovereign",
    "codex-sovereign",
    "avery-sovereign",  # 7th proposer also uses avery (strategist doubles up)
]

# Agent for critique (adversarial review)
CRITIC_AGENT = "sentinel-sovereign"


# ─────────────────────────────────────────────────────────────────────────────
# Proposal type
# ─────────────────────────────────────────────────────────────────────────────

class ProposalType:
    CODE_OPTIMIZATION = "code_optimization"
    MEMORY_TUNING     = "memory_tuning"
    AGENT_BEHAVIOR    = "agent_behavior"
    SECURITY_HARDENING = "security_hardening"
    PERFORMANCE       = "performance"
    LATENCY_REDUCTION = "latency_reduction"
    DOCUMENTATION     = "documentation"


# ─────────────────────────────────────────────────────────────────────────────
# Ollama call
# ─────────────────────────────────────────────────────────────────────────────

async def _llm(model: str, prompt: str, timeout: float = 90.0) -> str:
    """Call Ollama with a hard asyncio.wait_for guard so Windows ProactorEventLoop can't hang."""
    async def _do_call() -> str:
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=10.0)) as client:
            r = await client.post(_OLLAMA_URL, json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.4, "num_predict": 512},
            })
            if r.status_code == 200:
                return r.json().get("response", "").strip()
        return f"[{model}] unavailable"

    try:
        return await asyncio.wait_for(_do_call(), timeout=timeout + 15.0)
    except asyncio.TimeoutError:
        LOG.warning("[SAGE] LLM timed out after %.0fs (model=%s)", timeout, model)
        return f"[{model}] timeout"
    except Exception as e:
        LOG.debug("[SAGE] LLM call failed (%s): %s", model, e)
    return f"[{model}] unavailable"


# ─────────────────────────────────────────────────────────────────────────────
# State assessment
# ─────────────────────────────────────────────────────────────────────────────

async def _assess_state() -> Dict:
    """
    Detect system inefficiencies and opportunities for improvement.
    Returns a state dict with findings.
    """
    findings = {}

    # Memory stats
    try:
        from memory.ghostrecall import ghost
        mem_stats = ghost.stats()
        findings["memory"] = mem_stats
        # Flag if Engram Vault is getting large
        if mem_stats.get("engram_vault", 0) > 200:
            findings["memory_pressure"] = True
        if mem_stats.get("explicit_active", 0) > 400:
            findings["context_overflow_risk"] = True
    except Exception as e:
        LOG.debug("[SAGE] Memory stats error: %s", e)
        findings["memory"] = {"error": str(e)}

    # Iron Dome chain validity
    try:
        from memory.iron_dome import dome_verify
        chain_ok, errors = dome_verify()
        findings["chain_valid"] = chain_ok
        if not chain_ok:
            findings["chain_errors"] = errors[:3]
    except Exception:
        findings["chain_valid"] = None

    # Triage governor
    try:
        from memory.triage_governor import governor
        findings["triage"] = governor.stats()
    except Exception:
        pass

    # GitOps stats
    try:
        mutator = GitOpsMutator.instance()
        findings["gitops"] = mutator.stats()
    except Exception:
        pass

    # Verification stats
    try:
        verifier = VerificationPipeline.instance()
        findings["verification"] = verifier.stats()
    except Exception:
        pass

    return findings


# ─────────────────────────────────────────────────────────────────────────────
# Proposal generation
# ─────────────────────────────────────────────────────────────────────────────

async def _generate_proposals(
    state: Dict,
    cycle_number: int,
    goal: str,
) -> List[Dict]:
    """
    Generate PROPOSERS_PER_CYCLE proposals in parallel.
    Each proposer is a different agent (or role).
    """
    state_summary = json.dumps({
        k: v for k, v in state.items()
        if k not in ("chain_errors",)
    }, default=str)[:600]

    async def _one_proposal(agent: str, proposer_idx: int) -> Dict:
        focus_areas = [
            "Optimise memory recall latency",
            "Reduce SAGE cycle overhead",
            "Improve agent task routing accuracy",
            "Harden security gate checks",
            "Improve GhostRecall context quality",
            "Reduce Iron Dome write contention",
            "Speed up Verification Pipeline",
        ]
        focus = focus_areas[proposer_idx % len(focus_areas)]

        prompt = f"""You are a specialist improvement agent in the Aethyro SAGE loop.
System state: {state_summary}
Cycle: {cycle_number}
Your focus: {focus}
Goal: {goal}

Generate ONE specific improvement proposal. Include:
PROPOSAL_TYPE: <code_optimization|memory_tuning|agent_behavior|security_hardening|performance|documentation>
TITLE: <short title>
DESCRIPTION: <2-3 sentences: what, why, expected impact>
FILE: <relative file path to modify, or 'none'>
CODE: <Python code block if applicable, else 'none'>
EXPECTED_IMPROVEMENT: <measurable metric e.g. '20% latency reduction'>
RISK: <one main risk>

Be specific and actionable. No vague suggestions."""

        t0 = time.time()
        response = await _llm(agent, prompt, timeout=60.0)

        # Parse structured output
        proposal = {
            "proposal_id":  str(uuid.uuid4())[:10],
            "proposer":     agent,
            "proposer_idx": proposer_idx,
            "cycle":        cycle_number,
            "raw":          response,
            "created_at":   time.time(),
            "latency_ms":   round((time.time() - t0) * 1000, 1),
        }

        for line in response.splitlines():
            s = line.strip()
            for field in ["PROPOSAL_TYPE", "TITLE", "DESCRIPTION", "FILE",
                          "EXPECTED_IMPROVEMENT", "RISK"]:
                if s.startswith(f"{field}:"):
                    proposal[field.lower()] = s[len(field)+1:].strip()

        # Extract code block
        import re
        m = re.search(r"```python\n(.*?)```", response, re.DOTALL)
        proposal["code_block"] = m.group(1).strip() if m else None

        return proposal

    # Run all proposers in parallel
    tasks = [
        _one_proposal(PROPOSER_AGENTS[i % len(PROPOSER_AGENTS)], i)
        for i in range(PROPOSERS_PER_CYCLE)
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    proposals = []
    for r in results:
        if isinstance(r, Exception):
            LOG.warning("[SAGE] Proposer error: %s", r)
        else:
            proposals.append(r)

    return proposals


# ─────────────────────────────────────────────────────────────────────────────
# Adversarial critique
# ─────────────────────────────────────────────────────────────────────────────

async def _critique_proposal(proposal: Dict) -> Dict:
    """
    Sentinel-agent adversarial review of a proposal.
    Returns the proposal with critique_score added.
    """
    prompt = f"""You are SENTINEL, the adversarial security agent.
Review this improvement proposal and score it 0.0-1.0 for:
- Correctness (is the logic sound?)
- Safety (does it introduce vulnerabilities?)
- Impact (is the improvement real and meaningful?)

PROPOSAL TITLE: {proposal.get('title', proposal.get('TITLE', 'Unknown'))}
DESCRIPTION: {proposal.get('description', proposal.get('DESCRIPTION', ''))[:400]}
FILE: {proposal.get('file', proposal.get('FILE', 'none'))}
CODE SNIPPET: {str(proposal.get('code_block', ''))[:300]}

Output:
CRITIQUE: <2-sentence critique>
CORRECTNESS: <0.0-1.0>
SAFETY: <0.0-1.0>
IMPACT: <0.0-1.0>
CRITIQUE_SCORE: <avg of above three>
VERDICT: APPROVE or REJECT"""

    response = await _llm(CRITIC_AGENT, prompt, timeout=60.0)

    import re
    def _extract(pattern: str, text: str, default: float = 0.5) -> float:
        m = re.search(pattern + r"[:\s]+([0-9]*\.?[0-9]+)", text, re.IGNORECASE)
        return min(1.0, max(0.0, float(m.group(1)))) if m else default

    critique_score = _extract("CRITIQUE_SCORE", response)
    proposal["critique_score"]   = critique_score
    proposal["critique_raw"]     = response[:400]
    proposal["critique_verdict"] = "APPROVE" if "APPROVE" in response.upper() else "REJECT"
    return proposal


# ─────────────────────────────────────────────────────────────────────────────
# SAGELoop
# ─────────────────────────────────────────────────────────────────────────────

class SAGELoop:
    """
    Self-Improvement Engine — runs SAGE cycles and manages the nightly schedule.
    """

    _instance: Optional["SAGELoop"] = None

    def __init__(self):
        self._cycle_number    = 0
        self._total_deployed  = 0
        self._cycle_reports: List[Dict] = []
        self._running         = False   # session-level (run_session)
        self._cycle_running   = False   # cycle-level (run_cycle)
        self._ws_queues: List[asyncio.Queue] = []

        self.kairos   = KAIROSEngine()
        self.verifier = VerificationPipeline.instance()
        self.meta     = MetaAgent.instance()
        self.mutator  = GitOpsMutator.instance()

    @classmethod
    def instance(cls) -> "SAGELoop":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _broadcast(self, event: Dict) -> None:
        """Send an event to all Honcho WebSocket subscribers."""
        payload = json.dumps(event)
        dead = []
        for q in self._ws_queues:
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                dead.append(q)
        for d in dead:
            self._ws_queues.remove(d)

    def add_ws_client(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=200)
        self._ws_queues.append(q)
        return q

    def remove_ws_client(self, q: asyncio.Queue) -> None:
        if q in self._ws_queues:
            self._ws_queues.remove(q)

    def _save_report(self, report: Dict) -> None:
        _HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_HISTORY_PATH, "a") as f:
            f.write(json.dumps(report) + "\n")

    async def run_cycle(self, goal: str = "") -> Dict:
        """
        Execute a single SAGE improvement cycle.
        Returns a cycle report dict.
        Always writes a cycle report to sage_history.jsonl, even on crash.
        """
        from memory.iron_dome import dome_write

        self._cycle_number += 1
        cycle_id = str(uuid.uuid4())[:8]
        cycle_num = self._cycle_number
        t0 = time.time()
        self._cycle_running = True   # cycle-level guard

        if not goal:
            goal = f"Improve Aethyro system performance and reliability (cycle {cycle_num})"

        LOG.info("[SAGE] == Cycle %d start == id=%s", cycle_num, cycle_id)
        self._broadcast({"event": "cycle_start", "cycle": cycle_num, "cycle_id": cycle_id, "goal": goal})

        report: Dict[str, Any] = {
            "cycle_id":            cycle_id,
            "cycle_number":        cycle_num,
            "goal":                goal,
            "started_at":          t0,
            "proposals_generated": 0,
            "proposals_approved":  0,
            "proposals_deployed":  0,
            "proposals_failed":    0,
            "avg_score":           0.0,
            "common_failures":     [],
            "meta_rewrite":        False,
        }

        # ── Step 1: State Assessment ──────────────────────────────────────────
        LOG.info("[SAGE] Step 1: State assessment")
        self._broadcast({"event": "step", "step": 1, "name": "state_assessment", "cycle": cycle_num})
        state = await _assess_state()
        report["state"] = {k: str(v)[:100] for k, v in state.items()}

        # ── Step 2: Strategic Mapping (KAIROS quick plan) ─────────────────────
        LOG.info("[SAGE] Step 2: Strategic mapping (KAIROS)")
        self._broadcast({"event": "step", "step": 2, "name": "strategic_mapping", "cycle": cycle_num})
        kairos_plan = await self.kairos.quick_plan(
            goal,
            phases=[KAIROSPhase.KICKOFF, KAIROSPhase.ALIGN, KAIROSPhase.IMPLEMENT],
        )
        strategic_context = kairos_plan.to_markdown()[:800]

        # ── Step 3: Parallel Proposal Generation ─────────────────────────────
        LOG.info("[SAGE] Step 3: Generating %d proposals in parallel", PROPOSERS_PER_CYCLE)
        self._broadcast({"event": "step", "step": 3, "name": "proposal_generation",
                         "cycle": cycle_num, "count": PROPOSERS_PER_CYCLE})
        proposals = await _generate_proposals(state, cycle_num, strategic_context)
        report["proposals_generated"] = len(proposals)

        # ── Step 4: Group Evolution (Adversarial Critique) ────────────────────
        LOG.info("[SAGE] Step 4: Adversarial critique of %d proposals", len(proposals))
        self._broadcast({"event": "step", "step": 4, "name": "group_evolution", "cycle": cycle_num})
        critique_tasks = [_critique_proposal(p) for p in proposals]
        critiqued = await asyncio.gather(*critique_tasks, return_exceptions=True)
        proposals = [c for c in critiqued if not isinstance(c, Exception)]

        # Sort by critique score descending
        proposals.sort(key=lambda p: p.get("critique_score", 0), reverse=True)
        # Take top 3 for verification
        elite_proposals = [p for p in proposals if p.get("critique_score", 0) >= 0.65][:3]

        # ── Step 5: Verification Gate ─────────────────────────────────────────
        LOG.info("[SAGE] Step 5: Verification gate for %d elite proposals", len(elite_proposals))
        self._broadcast({"event": "step", "step": 5, "name": "verification",
                         "cycle": cycle_num, "candidates": len(elite_proposals)})

        scores = []
        deployed = []
        failures = []

        for proposal in elite_proposals:
            prop_id = proposal["proposal_id"]
            prop_text = (
                f"Title: {proposal.get('title', proposal.get('TITLE', ''))}\n"
                f"Description: {proposal.get('description', proposal.get('DESCRIPTION', ''))}\n"
                f"File: {proposal.get('file', proposal.get('FILE', 'none'))}\n"
                f"Expected: {proposal.get('expected_improvement', '')}\n"
                f"Risk: {proposal.get('risk', '')}\n"
            )
            if proposal.get("code_block"):
                prop_text += f"\n```python\n{proposal['code_block'][:800]}\n```"

            # Hard 3-minute timeout per proposal to prevent Windows asyncio hang
            try:
                vr = await asyncio.wait_for(
                    self.verifier.verify(
                        proposal_text=prop_text,
                        proposal_id=prop_id,
                        code_block=proposal.get("code_block"),
                        goal=goal,
                    ),
                    timeout=180.0,
                )
            except asyncio.TimeoutError:
                LOG.warning("[SAGE] Proposal %s verification timed out (180s) -- skipping", prop_id)
                from .verification import VerificationResult
                vr = VerificationResult(
                    proposal_id=prop_id, passed=False, final_score=0.0, blocked_at="timeout"
                )
                failures.append(f"verify_timeout:{prop_id}")
            except Exception as exc:
                LOG.error("[SAGE] Proposal %s verification error: %s", prop_id, exc)
                from .verification import VerificationResult
                vr = VerificationResult(
                    proposal_id=prop_id, passed=False, final_score=0.0, blocked_at="exception"
                )
                failures.append(f"verify_error:{prop_id}")

            scores.append(vr.final_score)
            proposal["verification_score"] = vr.final_score
            proposal["verification_passed"] = vr.passed

            self._broadcast({
                "event":       "proposal_scored",
                "cycle":       cycle_num,
                "proposal_id": prop_id,
                "score":       vr.final_score,
                "passed":      vr.passed,
                "summary":     vr.summary(),
            })

            if vr.passed:
                report["proposals_approved"] += 1

                # ── Step 6: Swarm Propagation (GitOps) ──────────────────────
                target_file = proposal.get("file", proposal.get("FILE", ""))
                if (target_file and target_file.lower() not in ("none", "n/a", "")
                        and proposal.get("code_block")):
                    LOG.info("[SAGE] Step 6: Deploying via GitOps: %s", target_file)
                    self._broadcast({"event": "step", "step": 6, "name": "swarm_propagation",
                                     "cycle": cycle_num, "file": target_file})
                    try:
                        mut = await asyncio.wait_for(
                            self.mutator.mutate(
                                proposal_id=prop_id,
                                file_path=target_file,
                                patch_content=proposal["code_block"],
                                description=proposal.get("title", "SAGE improvement"),
                            ),
                            timeout=60.0,
                        )
                        if mut.success:
                            report["proposals_deployed"] += 1
                            self._total_deployed += 1
                            deployed.append({
                                "proposal_id": prop_id,
                                "file": target_file,
                                "commit": mut.commit_hash,
                            })
                            LOG.info("[SAGE] DEPLOYED: %s commit=%s", target_file, mut.commit_hash)
                            self._broadcast({
                                "event": "deployed",
                                "cycle": cycle_num,
                                "file": target_file,
                                "commit": mut.commit_hash,
                            })
                        else:
                            failures.append(f"deploy_failed:{target_file}")
                    except Exception as mut_err:
                        LOG.warning("[SAGE] GitOps deploy error: %s", mut_err)
                        failures.append(f"deploy_error:{target_file}")
                else:
                    # Approved but no deployable code — record as knowledge
                    LOG.info("[SAGE] APPROVED (no-code): %s", proposal.get("title", ""))
                    deployed.append({"proposal_id": prop_id, "type": "knowledge"})
            else:
                report["proposals_failed"] += 1
                failures.append(f"verify_failed:{vr.blocked_at or 'final_score'}")

        report["avg_score"]       = round(sum(scores) / max(1, len(scores)), 3)
        report["common_failures"] = list(set(failures))[:5]
        report["deployed"]        = deployed

        # ── Step 7: Meta-Agent ────────────────────────────────────────────────
        LOG.info("[SAGE] Step 7: Checking Meta-Agent trigger (cycle=%d)", cycle_num)
        self._broadcast({"event": "step", "step": 7, "name": "meta_agent", "cycle": cycle_num})
        self._cycle_reports.append(report)

        try:
            new_rules = await asyncio.wait_for(
                self.meta.maybe_rewrite(cycle_num, self._cycle_reports),
                timeout=120.0,
            )
            if new_rules:
                report["meta_rewrite"] = True
                self.kairos.reload_rules()
                self._broadcast({
                    "event":         "meta_rewrite",
                    "cycle":         cycle_num,
                    "rules_version": new_rules.get("version", "?"),
                    "rules_count":   len(new_rules.get("rules", [])),
                    "insights":      new_rules.get("last_insights", []),
                })
                LOG.info("[SAGE] Meta-Agent rewrote rules -> version=%d", new_rules.get("version", 0))
        except asyncio.TimeoutError:
            LOG.warning("[SAGE] Meta-Agent timed out (120s) -- skipping this cycle")
        except Exception as meta_err:
            LOG.warning("[SAGE] Meta-Agent error: %s", meta_err)

        # ── Finalise (always runs, even after partial failures) ───────────────
        elapsed = round(time.time() - t0, 2)
        report["elapsed_s"]   = elapsed
        report["finished_at"] = time.time()
        self._cycle_running   = False

        try:
            dome_write("SAGE", "cycle_complete", {
                "cycle_id":     cycle_id,
                "cycle_number": cycle_num,
                "deployed":     report["proposals_deployed"],
                "avg_score":    report["avg_score"],
                "elapsed_s":    elapsed,
            })
        except Exception as e:
            LOG.warning("[SAGE] Iron Dome cycle_complete write failed: %s", e)

        try:
            self._save_report(report)
        except Exception as e:
            LOG.error("[SAGE] Failed to save cycle report: %s", e)

        self._broadcast({
            "event":    "cycle_complete",
            "cycle":    cycle_num,
            "elapsed_s": elapsed,
            "deployed":  report["proposals_deployed"],
            "approved":  report["proposals_approved"],
            "avg_score": report["avg_score"],
        })

        LOG.info(
            "[SAGE] == Cycle %d complete == %.1fs | approved=%d deployed=%d avg_score=%.3f",
            cycle_num, elapsed, report["proposals_approved"],
            report["proposals_deployed"], report["avg_score"],
        )
        return report

    async def run_session(self, cycles: int = CYCLES_PER_SESSION) -> List[Dict]:
        """
        Run a full nightly session of `cycles` SAGE cycles.
        Returns list of cycle reports.
        """
        if self._running:
            LOG.warning("[SAGE] Session already running — skipping")
            return []

        self._running = True
        reports = []
        LOG.info("[SAGE] ==== Starting nightly session (%d cycles) ====", cycles)
        self._broadcast({"event": "session_start", "cycles": cycles, "ts": time.time()})

        for i in range(cycles):
            try:
                report = await self.run_cycle(
                    goal=f"Improve Aethyro system performance and reliability — cycle {self._cycle_number + 1}"
                )
                reports.append(report)
                # Brief pause between cycles to let Ollama breathe
                await asyncio.sleep(5)
            except Exception as e:
                LOG.error("[SAGE] Cycle %d error: %s", i + 1, e)
                reports.append({"error": str(e), "cycle": i + 1})

        self._running = False
        LOG.info("[SAGE] ==== Nightly session complete (%d cycles) ====", cycles)
        self._broadcast({"event": "session_complete", "cycles_run": len(reports), "ts": time.time()})
        return reports

    def _seconds_until_3am(self) -> float:
        """Calculate seconds until next 3:00 AM."""
        now = datetime.now()
        target = now.replace(hour=NIGHTLY_HOUR, minute=NIGHTLY_MINUTE, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        return (target - now).total_seconds()

    async def nightly_scheduler(self) -> None:
        """
        Background scheduler: waits until 3:00 AM then runs a full session.
        Runs indefinitely until cancelled.
        """
        LOG.info("[SAGE] Nightly scheduler started — first run at %02d:%02d",
                 NIGHTLY_HOUR, NIGHTLY_MINUTE)
        while True:
            wait_s = self._seconds_until_3am()
            LOG.info("[SAGE] Next session in %.1fh (%.0fs)", wait_s / 3600, wait_s)
            self._broadcast({
                "event": "scheduled",
                "next_run_in_s": round(wait_s),
                "next_run_at": datetime.now().replace(
                    hour=NIGHTLY_HOUR, minute=NIGHTLY_MINUTE
                ).isoformat(),
            })
            await asyncio.sleep(wait_s)
            await self.run_session()

    def history(self, limit: int = 20) -> List[Dict]:
        """Return the last N cycle reports."""
        if not _HISTORY_PATH.exists():
            return []
        lines = _HISTORY_PATH.read_text().strip().splitlines()
        results = []
        for line in reversed(lines[-limit:]):
            try:
                results.append(json.loads(line))
            except Exception:
                pass
        return results

    def status(self) -> Dict:
        wait_s = self._seconds_until_3am()
        return {
            "cycle_number":      self._cycle_number,
            "total_deployed":    self._total_deployed,
            "running":           self._running or self._cycle_running,
            "session_running":   self._running,
            "cycle_running":     self._cycle_running,
            "ws_clients":        len(self._ws_queues),
            "next_session_in_s": round(wait_s),
            "next_session_at":   (datetime.now() + timedelta(seconds=wait_s)).strftime("%H:%M"),
            "meta_stats":        MetaAgent.instance().stats(),
            "verification_stats": VerificationPipeline.instance().stats(),
            "gitops_stats":      GitOpsMutator.instance().stats(),
        }


# ─────────────────────────────────────────────────────────────────────────────
# Service entrypoint
# ─────────────────────────────────────────────────────────────────────────────

async def run_sage_loop_service() -> None:
    """
    Start the SAGE service: background triage + nightly scheduler.
    Called by the FastAPI lifespan or start_sage.py.
    """
    sage  = SAGELoop.instance()
    tasks = [sage.nightly_scheduler()]

    # Also start memory triage loop
    try:
        from memory.triage_governor import run_triage_loop
        tasks.append(run_triage_loop())
    except Exception as e:
        LOG.warning("[SAGE] Triage governor not started: %s", e)

    await asyncio.gather(*tasks)
