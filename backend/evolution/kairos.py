"""GH05T3 — KAIROS evolutionary cycle engine."""
from __future__ import annotations
import json
import os
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path

KAIROS_LOG      = Path("evolution/kairos_log.jsonl")
ELITE_THRESHOLD = float(os.environ.get("SAGE_ELITE_THRESHOLD", "0.90"))

# Strong refs for fire-and-forget background tasks (notify/auto-PR) so they
# aren't garbage-collected mid-flight — asyncio only holds a weak reference.
_background_tasks: set = set()


def _track_task(task) -> None:
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


@dataclass
class KAIROSCycle:
    id:                   int
    proposal:             str
    verdict:              str
    score:                float
    timestamp:            float = field(default_factory=time.time)
    is_elite:             bool  = False
    # Sentinel + entropy fields — populated when wired through OmegaLoop
    sentinel_viability:   float = 0.0
    entropy_drift:        float = 0.0
    agent_id:             str   = "unknown"
    # Per-cycle telemetry — populated by sage_enhanced.run_enhanced_sage_cycle
    latency_s:            float = 0.0
    token_count:          int   = 0

    def to_dict(self) -> dict:
        return asdict(self)


class KAIROS:
    """Records evolutionary cycles, maintains elite archive, persists to JSONL."""

    def __init__(self, elite_threshold: float = ELITE_THRESHOLD):
        self.elite_threshold = elite_threshold
        self._cycles: list[KAIROSCycle] = []
        self._elite:  list[KAIROSCycle] = []
        KAIROS_LOG.parent.mkdir(parents=True, exist_ok=True)

    def record_cycle(
        self,
        proposal:           str,
        verdict:            str,
        score:              float,
        sentinel_viability: float = 0.0,
        entropy_drift:      float = 0.0,
        agent_id:           str   = "unknown",
        latency_s:          float = 0.0,
        token_count:        int   = 0,
    ) -> KAIROSCycle:
        cycle = KAIROSCycle(
            id                  = len(self._cycles) + 1,
            proposal            = proposal,
            verdict             = verdict,
            score               = score,
            is_elite            = score >= self.elite_threshold,
            sentinel_viability  = sentinel_viability,
            entropy_drift       = entropy_drift,
            agent_id            = agent_id,
            latency_s           = latency_s,
            token_count         = token_count,
        )
        self._cycles.append(cycle)
        if cycle.is_elite:
            self._elite.append(cycle)

        # MAP-Elites archive — direct insertion of high-quality cycles
        if score >= 0.70:
            try:
                from evolution.map_elites import add as me_add
                latency_ms  = cycle.latency_s * 1000
                token_count = float(cycle.token_count)
                me_add(
                    solution  = [min(score, 1.0), token_count, latency_ms, 0.65, 0.90],
                    objective = score,
                    measures  = [min(score, 0.999), min(latency_ms, 29999.0),
                                 min(token_count, 1999.0)],
                )
            except Exception:
                pass

        with open(KAIROS_LOG, "a") as f:
            f.write(json.dumps(cycle.to_dict()) + "\n")

        # W&B — best-effort
        try:
            from integrations.wandb_logger import log_kairos_cycle
            log_kairos_cycle(
                cycle_id      = cycle.id,
                score         = cycle.score,
                is_elite      = cycle.is_elite,
                total_cycles  = len(self._cycles),
                elite_cycles  = len(self._elite),
                sentinel_v    = cycle.sentinel_viability,
                entropy_drift = cycle.entropy_drift,
            )
        except Exception:
            pass

        # Notify on elite — best-effort
        if cycle.is_elite:
            try:
                import asyncio
                from integrations.notifier import notify_elite_cycle
                try:
                    loop = asyncio.get_running_loop()
                    _track_task(loop.create_task(notify_elite_cycle(
                        cycle.id, cycle.score, cycle.proposal)))
                except RuntimeError:
                    pass
            except Exception:
                pass

        # Auto-PR on elite — best-effort GitHub draft PR with impl skeleton
        if cycle.is_elite:
            try:
                import asyncio
                from evolution.auto_pr import create_proposal_pr
                async def _fire_pr():
                    await create_proposal_pr(
                        proposal=cycle.proposal,
                        score=cycle.score,
                        cycle_id=cycle.id,
                        agent_id=cycle.agent_id,
                    )
                try:
                    loop = asyncio.get_running_loop()
                    _track_task(loop.create_task(_fire_pr()))
                except RuntimeError:
                    pass
            except Exception:
                pass

        return cycle

    @property
    def elite_archive(self) -> list[KAIROSCycle]:
        return list(self._elite)

    @property
    def stats(self) -> dict:
        scores    = [c.score for c in self._cycles]
        drifts    = [c.entropy_drift for c in self._cycles if c.entropy_drift > 0]
        viabs     = [c.sentinel_viability for c in self._cycles if c.sentinel_viability > 0]
        blocked   = [c for c in self._cycles if c.verdict == "SENTINEL_BLOCK"]
        base = {
            "total_cycles":       len(self._cycles),
            "elite_cycles":       len(self._elite),
            "sentinel_blocks":    len(blocked),
            "elite_threshold":    self.elite_threshold,
            "avg_score":          round(sum(scores) / len(scores), 4) if scores else 0.0,
            "avg_sentinel_v":     round(sum(viabs)  / len(viabs),  4) if viabs  else 0.0,
            "avg_entropy_drift":  round(sum(drifts) / len(drifts), 4) if drifts else 0.0,
        }
        try:
            from evolution.map_elites import archive_stats
            base["map_elites"] = archive_stats()
        except Exception:
            pass
        return base


# ---------------------------------------------------------------------------
# Module-level singleton + function API (used by evolution/__init__.py)
# ---------------------------------------------------------------------------
_kairos: KAIROS | None = None


def _get_kairos() -> KAIROS:
    global _kairos
    if _kairos is None:
        _kairos = KAIROS()
    return _kairos


def record_cycle(proposal: str = "", verdict: str = "PARTIAL", score: float = 0.0,
                 sentinel_viability: float = 0.0, entropy_drift: float = 0.0,
                 agent_id: str = "unknown", **kwargs) -> dict:
    """Module-level wrapper — records a cycle and returns the cycle dict."""
    cycle = _get_kairos().record_cycle(
        proposal           = proposal,
        verdict            = verdict,
        score              = score,
        sentinel_viability = sentinel_viability,
        entropy_drift      = entropy_drift,
        agent_id           = agent_id,
        **kwargs,
    )
    return cycle.to_dict()


def stats() -> dict:
    """Module-level wrapper — returns KAIROS stats dict."""
    return _get_kairos().stats


def ledger_summary() -> dict:
    """Module-level wrapper — returns elite archive summary."""
    k = _get_kairos()
    return {
        "entries":  len(k.elite_archive),
        "summary":  [c.to_dict() for c in k.elite_archive[-10:]],
    }
