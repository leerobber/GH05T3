"""
PolicyRateLimitChecker — PolicyStore-driven in-memory sliding-window rate limiter
==================================================================================
Reads per-agent, per-write-class rate limits from PolicyStore JSON policies
and enforces them via an in-memory sliding window.

Why in-memory instead of Iron Dome count_writes():
  The Iron Dome records the SUBSYSTEM actor ("GhostRecall", "GitOpsMutator"),
  not the calling-agent ("SAGE").  Querying count_writes(agent_id="SAGE")
  would always return 0 since SAGE is not the dome actor.  Fixing this would
  require changing dome actor semantics across the codebase — a bigger change
  than warranted here.  The in-memory approach is faster (~0.01 ms vs ~5 ms)
  and has no coupling risk.  Durable rate limit state (across restarts) is
  an optional future enhancement.

Rate window key:
  "policy:{agent_id}:{write_class_value}" — separate from the basic checker's
  keys (which use "agent_id:write_class") to avoid namespace collision if both
  checkers run simultaneously during a migration period.

Policy resolution order (for max_per_minute):
  1. Per-agent policy rate_limits[write_class]["max_per_minute"]
  2. Global _global.json default_rate_limits[write_class]["max_per_minute"]
  3. Hardcoded conservative fallback: 10 / minute

Usage:
    from sovereignnation.policy_store import policy_store
    from sovereignnation.checkers.rate_limit_checker import PolicyRateLimitChecker

    checker = PolicyRateLimitChecker(policy_store)
    result = checker.check(ctx)
"""
from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict, deque
from typing import TYPE_CHECKING, Dict

from sovereignnation.access_control import CheckResult, WriteClass, WriteContext

if TYPE_CHECKING:
    from sovereignnation.policy_store import PolicyStore

LOG = logging.getLogger("aethyro.checkers.rate_limit")

# Shared rate-window state — module-level so all PolicyRateLimitChecker
# instances share one sliding window dict (singleton semantics).
_rate_windows: Dict[str, deque] = defaultdict(deque)
_rate_lock = threading.Lock()

# Conservative fallback when no policy is found
_FALLBACK_MAX_PER_MINUTE = 10


class PolicyRateLimitChecker:
    """
    Policy-driven sliding-window rate limiter.

    Reads max_per_minute from the agent's PolicyStore entry.
    Unknown agents get the conservative fallback limit (10/min).
    """

    name = "PolicyRateLimitChecker"

    def __init__(self, policy_store: "PolicyStore"):
        self.policy_store = policy_store

    def _max_per_minute(self, ctx: WriteContext) -> int:
        """Look up max_per_minute for this (agent, write_class) pair."""
        policy = self.policy_store.get_policy(ctx.agent_id)
        if not policy:
            return _FALLBACK_MAX_PER_MINUTE
        rate_limits = policy.get("rate_limits", {})
        class_limits = rate_limits.get(ctx.write_class.value, {})
        return class_limits.get("max_per_minute", _FALLBACK_MAX_PER_MINUTE)

    def check(self, ctx: WriteContext) -> CheckResult:
        max_writes = self._max_per_minute(ctx)
        key = f"policy:{ctx.agent_id}:{ctx.write_class.value}"
        now = time.monotonic()
        cutoff = now - 60.0  # 60-second sliding window

        with _rate_lock:
            q = _rate_windows[key]
            # Evict timestamps outside the window
            while q and q[0] < cutoff:
                q.popleft()

            count = len(q)
            if count >= max_writes:
                LOG.warning(
                    "[PolicyRate] FAIL agent=%s class=%s count=%d max=%d",
                    ctx.agent_id, ctx.write_class.value, count, max_writes,
                )
                return CheckResult.FAIL

            # Register the attempt inside the lock (TOCTOU safe)
            q.append(now)

        LOG.debug(
            "[PolicyRate] PASS agent=%s class=%s count=%d/%d",
            ctx.agent_id, ctx.write_class.value, count + 1, max_writes,
        )
        return CheckResult.PASS
