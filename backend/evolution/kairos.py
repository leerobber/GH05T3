"""GH05T3 — KAIROS evolutionary cycle engine."""
from __future__ import annotations
import json
import os
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path

KAIROS_LOG      = Path("evolution/kairos_log.jsonl")
ELITE_THRESHOLD = float(os.environ.get("SAGE_ELITE_THRESHOLD", "0.90"))

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
        )
        self._cycles.append(cycle)
        if cycle.is_elite:
            self._elite.append(cycle)

        # MAP-Elites archive — quality-diversity storage (replaces flat elite list)
        try:
            from evolution.map_elites import get_archive
            get_archive().add(
                proposal    = proposal,
                quality     = score,
                latency_s   = getattr(cycle, "_latency_s",   0.0),
                token_count = getattr(cycle, "_token_count", 0),
                metadata    = {"cycle_id": cycle.id, "verdict": verdict,
                               "agent_id": agent_id},
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
                    loop.create_task(notify_elite_cycle(
                        cycle.id, cycle.score, cycle.proposal))
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
            from evolution.map_elites import get_archive
            base["map_elites"] = get_archive().stats()
        except Exception:
            pass
        return base
