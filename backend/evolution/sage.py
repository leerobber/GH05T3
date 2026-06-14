"""GH05T3 — SAGE validation engine + MAP-Elites evaluator.

Module-level evaluator functions (used by ghost_llm.py SAGE wiring):
    evaluate_cycle(result, latency_ms, token_count) → dict
    should_archive(eval_result) → bool
    adapt_prompt_for_target(base_prompt, target) → str

SAGE class (used by kairos.py and omega_loop.py):
    SAGE.evaluate(proposal, ...) → dict with verdict/score/sentinel fields
"""
from __future__ import annotations
import time


# ---------------------------------------------------------------------------
# Module-level evaluator — converts run_sage_cycle() output to archive metrics
# ---------------------------------------------------------------------------

def evaluate_cycle(result: dict, latency_ms: float, token_count: int) -> dict:
    """Convert a SAGE cycle result dict into MAP-Elites archive metrics."""
    final_score = float(result.get("final_score", 0.0))
    verdict     = result.get("verdict", "PARTIAL")
    decision    = result.get("critic_decision", "REVISE")

    quality  = final_score
    base_map = {"PASS": 1.0, "PARTIAL": 0.6, "FAIL": 0.2}
    mult_map = {"APPROVE": 1.0, "REJECT": 0.5, "REVISE": 0.75}
    composite = final_score * base_map.get(verdict, 0.6) * mult_map.get(decision, 0.75)

    measures = [
        min(max(quality,           0.0), 0.999),
        min(max(float(latency_ms), 0.0), 29999.0),
        min(max(float(token_count),0.0), 1999.0),
    ]
    solution = [
        min(max(quality, 0.0), 1.0),
        float(token_count),
        float(latency_ms),
        0.65,
        0.90,
    ]
    return {
        "solution":    solution,
        "objective":   float(composite),
        "measures":    measures,
        "quality":     quality,
        "latency_ms":  float(latency_ms),
        "token_count": int(token_count),
        "archived":    final_score >= 0.70 or verdict == "PASS",
        "elite":       final_score >= 0.85,
    }


def should_archive(eval_result: dict) -> bool:
    return bool(eval_result.get("archived", False))


def adapt_prompt_for_target(base_prompt: str, target: dict) -> str:
    """Inject MAP-Elites quality/latency/token targets into a proposer prompt."""
    q_target   = float(target.get("quality_target", 0.75))
    t_budget   = int(target.get("token_budget", 400))
    l_target   = float(target.get("latency_target", 15000))
    word_limit = max(8, int(t_budget / 1.3))

    if q_target >= 0.85:
        style = "Aim for high-impact, specific, immediately shippable code or config changes."
    elif q_target >= 0.60:
        style = "Aim for concrete, novel exploration with measurable improvement."
    else:
        style = "Explore creative territory. Unconventional angles are acceptable."

    return (
        base_prompt
        + f"\n\n[EVOLUTION TARGETS - cycle {target.get('_cycle_num', '?')}]\n"
        + f"Quality tier: {q_target:.2f} | {style}\n"
        + f"Keep response under {word_limit} words, roughly {t_budget} tokens.\n"
        + f"Latency budget: {l_target:.0f}ms. Be concise."
    )


class SAGE:
    """Self-Assessing Generative Evaluator — validates Omega Loop outputs."""

    def __init__(self, sentinel_enabled: bool = True):
        self._evals           = 0
        self._passes          = 0
        self._revises         = 0
        self._sentinel_blocks = 0
        self._boot            = time.time()
        self._sentinel_enabled = sentinel_enabled

    def evaluate(self, proposal: str, query: str = "",
                 entropy_drift: float = 0.0, human_sig: int = 1) -> dict:
        """Score a proposal and run it through the Sentinel gate.

        Args:
            proposal:      response text to evaluate
            query:         original user message (reserved for future learned scoring)
            entropy_drift: cosine drift from EntropyDriftTracker (D_ε in V_E)
            human_sig:     1 = normal operation, 0 = kill switch engaged
        """
        self._evals += 1
        score = min(1.0, len(proposal.split()) / 100)

        sentinel_result: dict = {"authorized": True, "viability": 1.0,
                                  "compute_cost": 0.0}
        if self._sentinel_enabled:
            try:
                from security.sentinel import evaluate_cycle
                sentinel_result = evaluate_cycle(
                    sage_score    = score,
                    response      = proposal,
                    entropy_drift = entropy_drift,
                    human_sig     = human_sig,
                )
            except ImportError:
                pass  # sentinel module not available — degrade gracefully

        authorized = sentinel_result.get("authorized", True)

        if score >= 0.5 and authorized:
            verdict = "PASS"
            self._passes += 1
        elif not authorized:
            verdict = "SENTINEL_BLOCK"
            self._sentinel_blocks += 1
        else:
            verdict = "REVISE"
            self._revises += 1

        return {
            "verdict":             verdict,
            "score":               round(score, 3),
            "critique":            "",
            "sentinel_viability":  sentinel_result.get("viability", 0.0),
            "sentinel_authorized": authorized,
            "entropy_drift":       round(entropy_drift, 4),
        }

    @property
    def stats(self) -> dict:
        return {
            "total_evals":      self._evals,
            "passes":           self._passes,
            "revises":          self._revises,
            "sentinel_blocks":  self._sentinel_blocks,
            "pass_rate":        round(self._passes / self._evals, 3) if self._evals else 0.0,
            "uptime":           time.time() - self._boot,
        }

    async def close(self):
        pass
