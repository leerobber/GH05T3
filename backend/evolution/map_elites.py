"""MAP-Elites quality-diversity archive for GH05T3 SAGE cycle optimization.

Replaces KAIROS's flat elite list with a pyribs GridArchive indexed by
three behavior dimensions:
    quality  — SAGE final_score            (0.0 – 1.0, 10 cells)
    latency  — normalized response time    (0.0 – 1.0, 5 cells, 0=fast)
    cost     — normalized token count      (0.0 – 1.0, 5 cells, 0=cheap)

The objective stored in each cell is the quality score.  The archive
therefore keeps the BEST-quality proposal for each (quality, latency, cost)
region of behavior space rather than a single global elite list.

GA / emitter path:
    ask()  → GaussianEmitter proposes parameter perturbations for next batch
    tell() → scheduler updates archive after evaluation

Config env vars:
    ME_QUALITY_CELLS   10   — quality dimension grid resolution
    ME_LATENCY_CELLS   5    — latency dimension grid resolution
    ME_COST_CELLS      5    — cost dimension grid resolution
    ME_SIGMA           0.1  — mutation_rate (GaussianEmitter σ)
    ME_BATCH_SIZE      10   — population_size (candidates per ask())
    ME_LATENCY_CAP     30   — seconds → normalised to 1.0
    ME_TOKEN_CAP       2000 — tokens → normalised to 1.0
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

import numpy as np

LOG = logging.getLogger("ghost.map_elites")

_Q_CELLS    = int(os.environ.get("ME_QUALITY_CELLS",  "10"))
_L_CELLS    = int(os.environ.get("ME_LATENCY_CELLS",  "5"))
_C_CELLS    = int(os.environ.get("ME_COST_CELLS",     "5"))
_SIGMA      = float(os.environ.get("ME_SIGMA",        "0.1"))
_BATCH      = int(os.environ.get("ME_BATCH_SIZE",     "10"))
_LAT_CAP    = float(os.environ.get("ME_LATENCY_CAP",  "30"))
_TOK_CAP    = float(os.environ.get("ME_TOKEN_CAP",    "2000"))

# Solution vector: [quality_score, norm_latency, norm_cost]
_SOL_DIM = 3


@dataclass
class ArchiveEntry:
    proposal:    str
    quality:     float
    latency_s:   float
    token_count: int
    cell:        tuple[int, ...]
    metadata:    dict


class MAPElitesArchive:
    """Quality-diversity archive for SAGE evolutionary cycles.

    Primary path (pyribs installed):
        - GridArchive stores best solution per behavior cell
        - GaussianEmitter mutates solutions (σ = mutation_rate)
        - Scheduler ties ask/tell together

    Fallback (pyribs not installed):
        - Simple threshold list (identical to pre-integration behaviour)
        - All public API remains identical
    """

    def __init__(self):
        self._ribs_ok   = False
        self._archive   = None
        self._scheduler = None
        self._fallback: list[ArchiveEntry] = []

        try:
            from ribs.archives import GridArchive
            from ribs.emitters import GaussianEmitter
            from ribs.schedulers import Scheduler

            self._archive = GridArchive(
                solution_dim = _SOL_DIM,
                dims         = [_Q_CELLS, _L_CELLS, _C_CELLS],
                ranges       = [(0.0, 1.0), (0.0, 1.0), (0.0, 1.0)],
                qd_score_offset = -1.0,
                seed         = 42,
            )
            emitters = [
                GaussianEmitter(
                    archive    = self._archive,
                    sigma      = _SIGMA,
                    batch_size = _BATCH,
                    x0         = np.array([0.5, 0.3, 0.3]),
                )
            ]
            self._scheduler = Scheduler(self._archive, emitters)
            self._ribs_ok   = True
            LOG.info("[map-elites] pyribs GridArchive %dx%dx%d cells σ=%.2f batch=%d",
                     _Q_CELLS, _L_CELLS, _C_CELLS, _SIGMA, _BATCH)
        except ImportError:
            LOG.warning("[map-elites] pyribs not installed (pip install ribs) — "
                        "falling back to threshold archive")
        except Exception as e:
            LOG.warning("[map-elites] pyribs init failed (%s) — using fallback", e)

    # ── public API ────────────────────────────────────────────────────────────

    def add(self, proposal: str, quality: float, latency_s: float = 0.0,
            token_count: int = 0, metadata: dict | None = None) -> bool:
        """Record a SAGE cycle result.

        Returns True if this solution improved its archive cell (new elite).
        """
        lat_norm  = min(1.0, latency_s   / max(_LAT_CAP, 1e-6))
        cost_norm = min(1.0, token_count / max(_TOK_CAP, 1.0))
        solution  = np.array([quality, lat_norm, cost_norm])
        measures  = solution.copy()   # behavior = solution for now

        if self._ribs_ok:
            old_n = self._archive.stats.num_elites
            self._archive.add(
                solution  = solution,
                objective = float(quality),
                measures  = measures,
            )
            improved = self._archive.stats.num_elites > old_n or quality > (
                self._archive.stats.obj_max or 0.0
            )
        else:
            improved = quality >= 0.85
            if improved:
                self._fallback.append(ArchiveEntry(
                    proposal    = proposal[:400],
                    quality     = quality,
                    latency_s   = latency_s,
                    token_count = token_count,
                    cell        = (),
                    metadata    = metadata or {},
                ))

        if improved:
            LOG.debug("[map-elites] new elite q=%.3f lat=%.2fs tok=%d",
                      quality, latency_s, token_count)
        return improved

    def ask(self) -> list[dict] | None:
        """Request next batch of candidate parameter vectors from the emitter.

        Returns a list of dicts describing perturbation targets, or None if
        pyribs is not available.  These are used to seed the next SAGE round:
          quality_target  — aim for this score
          latency_budget  — seconds available
          token_budget    — tokens available
        """
        if not self._ribs_ok:
            return None
        try:
            solutions = self._scheduler.ask()
            return [
                {
                    "quality_target":  float(np.clip(s[0], 0.0, 1.0)),
                    "latency_budget":  float(np.clip(s[1], 0.0, 1.0)) * _LAT_CAP,
                    "token_budget":    int(np.clip(s[2], 0.0, 1.0) * _TOK_CAP),
                }
                for s in solutions
            ]
        except Exception as e:
            LOG.warning("[map-elites] ask() failed: %s", e)
            return None

    def tell(self, objectives: list[float], latencies: list[float],
             token_counts: list[int]) -> None:
        """Feed evaluation results back to the scheduler after ask().

        Call once per ask() with matching-length lists.
        """
        if not self._ribs_ok or self._scheduler is None:
            return
        try:
            measures = [
                np.array([q, min(1.0, l / _LAT_CAP), min(1.0, t / _TOK_CAP)])
                for q, l, t in zip(objectives, latencies, token_counts)
            ]
            self._scheduler.tell(objectives, measures)
        except Exception as e:
            LOG.warning("[map-elites] tell() failed: %s", e)

    # ── statistics ────────────────────────────────────────────────────────────

    @property
    def num_elites(self) -> int:
        if self._ribs_ok:
            return self._archive.stats.num_elites
        return len(self._fallback)

    def stats(self) -> dict:
        if self._ribs_ok:
            s = self._archive.stats
            return {
                "backend":    "pyribs",
                "num_elites": s.num_elites,
                "qd_score":   round(float(s.qd_score), 4),
                "obj_max":    round(float(s.obj_max),  4) if s.num_elites else 0.0,
                "obj_mean":   round(float(s.obj_mean), 4) if s.num_elites else 0.0,
                "cells":      [_Q_CELLS, _L_CELLS, _C_CELLS],
                "sigma":      _SIGMA,
                "batch_size": _BATCH,
            }
        return {
            "backend":    "threshold",
            "num_elites": len(self._fallback),
            "obj_max":    max((e.quality for e in self._fallback), default=0.0),
        }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
_archive: MAPElitesArchive | None = None


def get_archive() -> MAPElitesArchive:
    global _archive
    if _archive is None:
        _archive = MAPElitesArchive()
    return _archive
