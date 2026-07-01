"""
Prometheus metrics for the OSS / MVS layer.

Exposed via GET /oss/metrics and merged into gateway /metrics when mounted.

Signals (iron-foundation quick win):
- gh05t3_mvs_cycle_duration_seconds — histogram of run_cycle / HTTP cycle latency
- gh05t3_mvs_cycles_total — counter by dry_run outcome
- gh05t3_marketplace_operations_total — buy/list successes
- gh05t3_marketplace_failures_total — guarded marketplace errors by operation
"""
from __future__ import annotations

import time
from typing import Any

_HAS_PROM = False
_CYCLE_DURATION = None
_CYCLES_TOTAL = None
_MARKETPLACE_OPS = None
_MARKETPLACE_FAILURES = None
_VOLATILITY_PRESSURE = None


def _register():
    global _HAS_PROM, _CYCLE_DURATION, _CYCLES_TOTAL, _MARKETPLACE_OPS, _MARKETPLACE_FAILURES, _VOLATILITY_PRESSURE
    if _CYCLE_DURATION is not None:
        return
    try:
        from prometheus_client import Counter, Histogram, REGISTRY
    except ImportError:
        return

    def _histogram(name: str, doc: str):
        try:
            return Histogram(name, doc, ["dry_run"])
        except ValueError:
            return REGISTRY._names_to_collectors.get(name)

    def _counter(name: str, doc: str, labels: list[str] | None = None):
        try:
            return Counter(name, doc, labels or [])
        except ValueError:
            return REGISTRY._names_to_collectors.get(name)

    _CYCLE_DURATION = _histogram(
        "gh05t3_mvs_cycle_duration_seconds",
        "MVS cycle wall-clock duration",
    )
    _CYCLES_TOTAL = _counter(
        "gh05t3_mvs_cycles_total",
        "MVS cycles completed",
        ["dry_run", "outcome"],
    )
    _MARKETPLACE_OPS = _counter(
        "gh05t3_marketplace_operations_total",
        "Successful marketplace buy/list operations",
        ["operation"],
    )
    _MARKETPLACE_FAILURES = _counter(
        "gh05t3_marketplace_failures_total",
        "Marketplace operation failures (guarded paths)",
        ["operation"],
    )
    _VOLATILITY_PRESSURE = _counter(
        "gh05t3_volatility_pressure_cycles_total",
        "Theory Lab evolutionary pressure cycles",
        ["outcome"],
    )
    _HAS_PROM = True


_register()


def record_cycle(duration_sec: float, *, dry_run: bool = False, outcome: str = "ok") -> None:
    _register()
    label = "true" if dry_run else "false"
    if _CYCLE_DURATION is not None:
        _CYCLE_DURATION.labels(dry_run=label).observe(max(0.0, duration_sec))
    if _CYCLES_TOTAL is not None:
        _CYCLES_TOTAL.labels(dry_run=label, outcome=outcome).inc()


def record_marketplace_success(operation: str) -> None:
    _register()
    if _MARKETPLACE_OPS is not None:
        _MARKETPLACE_OPS.labels(operation=operation).inc()


def record_marketplace_failure(operation: str) -> None:
    _register()
    if _MARKETPLACE_FAILURES is not None:
        _MARKETPLACE_FAILURES.labels(operation=operation).inc()


def record_volatility_pressure(
    *,
    cycle: int,
    top_agents: int,
    spawn_boost: int,
    pareto_ratio: float,
) -> None:
    """Log Phase 2 evolutionary pressure metrics (Prometheus when available)."""
    _register()
    outcome = "boost" if spawn_boost > 0 else "neutral"
    if _VOLATILITY_PRESSURE is not None:
        _VOLATILITY_PRESSURE.labels(outcome=outcome).inc()
    _ = (cycle, top_agents, pareto_ratio)


class _CycleTimer:
    def __init__(self, *, dry_run: bool = False):
        self.dry_run = dry_run
        self._t0 = 0.0
        self.outcome = "ok"

    def __enter__(self):
        self._t0 = time.monotonic()
        return self

    def __exit__(self, exc_type, exc, tb):
        record_cycle(
            time.monotonic() - self._t0,
            dry_run=self.dry_run,
            outcome="error" if exc_type else self.outcome,
        )
        return False


def cycle_timer(*, dry_run: bool = False) -> _CycleTimer:
    return _CycleTimer(dry_run=dry_run)


def metrics_payload() -> tuple[bytes | dict[str, Any], str]:
    """
    Returns (body, media_type).
    Prometheus text when prometheus_client is installed; JSON snapshot otherwise.
    """
    _register()
    if _HAS_PROM:
        from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

        return generate_latest(), CONTENT_TYPE_LATEST

    return {
        "gh05t3_mvs_cycle_duration_seconds": "unavailable (install prometheus-client)",
        "gh05t3_marketplace_failures_total": "unavailable",
        "note": "pip install prometheus-client>=0.20.0",
    }, "application/json"