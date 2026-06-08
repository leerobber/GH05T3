"""
IBAC Access Control — Parallel Macro Checker Enforcement
=========================================================
Implements the 2-of-3 / 3-of-3 quorum gate that guards all write paths
in-process, without relying on network calls to the IBAC daemon (port 8112).

Why in-process macro checkers instead of network calls to the daemon:
  Same process, same OS user → a localhost TCP socket adds ZERO OS-level trust
  boundary.  An agent that can call the daemon can also bypass it by importing
  Python directly.  The only real boundary is a separate OS user + filesystem
  ACLs.  Given that constraint, in-process enforcement is strictly better:

    - Parallel thread execution: all 3 checkers run concurrently (~0.2 ms total)
    - No fragility from daemon restart lag
    - No latency budget lost to TCP round-trips on every write
    - Same audit trail: every denial writes to Iron Dome

Architecture
------------
Three checkers, each implementing MacroChecker Protocol:

  RateLimitChecker  — in-memory sliding window per (agent_id, write_class)
                      Fast (~0.01 ms, no I/O, no external deps)

  SignatureChecker  — HMAC-SHA256 verify against the master key
                      Same key as gitops_mutator + ibac_daemon

  ACLChecker        — CAPABILITY_POLICY lookup from ibac_policy.py
                      O(1) dict lookup, no I/O

QuorumGate(checkers, required_passes=N):
  .enforce(ctx)       — sync, sequential  (for sync callers)
  .enforce_async(ctx) — async, all three checkers run in parallel thread-pool

Pre-built gate instances (import these):
  gitops_gate  — required_passes=3  (ALL must pass: highest-risk, file + git)
  memory_gate  — required_passes=2  (signature optional: memory writes rarely
                                     carry a pre-computed MAC)

Usage
-----
    from sovereignnation.access_control import (
        WriteClass, WriteContext, gitops_gate, memory_gate
    )

    # GitOpsMutator.mutate() — after SIGN, before WRITE (passes full HMAC):
    ctx = WriteContext(
        agent_id="GitOpsMutator",
        proposal_id=proposal_id,
        write_class=WriteClass.GITOPS_MUTATION,
        target_path=file_path,
        payload_summary=description,
        metadata={"mac_payload": sign_payload, "mac": signature},
    )
    await gitops_gate.enforce_async(ctx)   # raises PermissionError if denied

    # GhostRecall.store() — before SQLite insert (no MAC for memory writes):
    ctx = WriteContext(
        agent_id=agent_id,
        proposal_id=mem_id,
        write_class=WriteClass.GHOST_RECALL,
        target_path=f"memory/{agent_id}",
        payload_summary=content[:120],
        metadata={},
    )
    await memory_gate.enforce_async(ctx)   # 2-of-3: ACL + RateLimit sufficient
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

LOG = logging.getLogger("aethyro.access_control")

# Shared HMAC master key — same file used by gitops_mutator and ibac_daemon.
# All three modules load the key independently to avoid circular imports.
_KEY_PATH = Path(__file__).parent.parent / "kairos" / "data" / "gitops_master.key"


def _load_key() -> Optional[bytes]:
    """Load the HMAC-SHA256 master key from disk (cached per call — file is tiny)."""
    if _KEY_PATH.exists():
        try:
            return bytes.fromhex(_KEY_PATH.read_text().strip())
        except Exception:
            pass
    return None


def _verify_hmac(data: str, signature: str) -> bool:
    """
    Constant-time HMAC-SHA256 verification.
    Returns True if key file is absent (dev mode — no key → open).
    Returns True if the HMAC matches, False otherwise.
    """
    key = _load_key()
    if not key:
        return True  # dev mode: no key → allow everything
    expected = hmac.new(key, data.encode("utf-8"), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


# ─────────────────────────────────────────────────────────────────────────────
# Data types
# ─────────────────────────────────────────────────────────────────────────────

class WriteClass(Enum):
    """Category of write operation — controls which gate and rate-limits apply."""
    DOME_APPEND     = "DOME_APPEND"       # append to Iron Dome audit chain
    GITOPS_MUTATION = "GITOPS_MUTATION"   # file write + git commit
    GHOST_RECALL    = "GHOST_RECALL"      # memory layer write


@dataclass
class WriteContext:
    """
    Full context passed to every MacroChecker.

    metadata keys (optional — used by specific checkers):
      "mac_payload": str  — raw string that was HMAC-signed by the caller
      "mac":         str  — full 64-hex HMAC-SHA256 signature
    """
    agent_id:        str
    proposal_id:     str            # SAGE proposal ID or short UUID for standalone writes
    write_class:     WriteClass
    target_path:     str            # file path or memory namespace (e.g. "memory/SAGE")
    payload_summary: str            # 1-line human-readable description, max 120 chars
    metadata:        Dict[str, Any] = field(default_factory=dict)


class CheckResult(Enum):
    PASS = "PASS"
    FAIL = "FAIL"


@runtime_checkable
class MacroChecker(Protocol):
    """Protocol: any object with a synchronous .check(WriteContext) → CheckResult."""
    name: str

    def check(self, ctx: WriteContext) -> CheckResult:
        ...


# ─────────────────────────────────────────────────────────────────────────────
# Checker 1: Rate Limit — in-memory sliding window
# ─────────────────────────────────────────────────────────────────────────────

# Keyed by "agent_id:write_class_value" → deque of monotonic timestamps
_rate_windows: Dict[str, deque] = defaultdict(deque)
_rate_lock = threading.Lock()

# (max_writes, window_seconds) per WriteClass
RATE_LIMITS: Dict[WriteClass, tuple] = {
    WriteClass.GITOPS_MUTATION: (10,  60.0),   # 10 mutations / min  — strict
    WriteClass.GHOST_RECALL:    (100, 60.0),   # 100 memories / min  — generous
    WriteClass.DOME_APPEND:     (500, 60.0),   # 500 audits   / min  — effectively unlimited
}


class RateLimitChecker:
    """
    Sliding-window rate limiter per (agent_id, write_class).

    Uses an in-memory deque protected by a threading.Lock — safe across
    asyncio tasks running on the same OS thread and across threadpool workers.
    No I/O.  Typical latency: ~0.01 ms.
    """

    name = "RateLimitChecker"

    def check(self, ctx: WriteContext) -> CheckResult:
        max_writes, window_s = RATE_LIMITS.get(ctx.write_class, (50, 60.0))
        key = f"{ctx.agent_id}:{ctx.write_class.value}"
        now = time.monotonic()
        cutoff = now - window_s

        with _rate_lock:
            q = _rate_windows[key]
            # Evict timestamps outside the sliding window
            while q and q[0] < cutoff:
                q.popleft()
            count = len(q)
            if count >= max_writes:
                LOG.warning(
                    "[IBAC:RateLimit] FAIL agent=%s class=%s count=%d max=%d",
                    ctx.agent_id, ctx.write_class.value, count, max_writes,
                )
                return CheckResult.FAIL
            # Register this attempt inside the lock (not after) to prevent TOCTOU
            q.append(now)

        return CheckResult.PASS


# ─────────────────────────────────────────────────────────────────────────────
# Checker 2: Signature — HMAC-SHA256 verify
# ─────────────────────────────────────────────────────────────────────────────

class SignatureChecker:
    """
    Verifies that the write context carries a valid HMAC-SHA256 MAC.

    Reads from ctx.metadata:
      "mac_payload" — the string that was signed by the caller
      "mac"         — the full 64-hex HMAC digest

    Behaviour matrix:
      Key absent on disk + no MAC   → PASS  (dev mode, no key file)
      Key present  + no MAC         → FAIL  (MAC required but missing)
      Key present  + wrong MAC      → FAIL  (tampered or wrong key)
      Key present  + correct MAC    → PASS

    For memory_gate (required_passes=2): one FAIL here is tolerable if
    ACL + RateLimit both pass.
    For gitops_gate (required_passes=3): ALL must pass, so callers MUST
    provide mac_payload + mac in ctx.metadata.
    """

    name = "SignatureChecker"

    def check(self, ctx: WriteContext) -> CheckResult:
        mac_payload = ctx.metadata.get("mac_payload")
        mac         = ctx.metadata.get("mac")
        key_exists  = _KEY_PATH.exists()

        if not mac_payload or not mac:
            if not key_exists:
                # Dev mode — no key on disk means open enforcement
                return CheckResult.PASS
            LOG.debug(
                "[IBAC:Signature] FAIL — no MAC in metadata (agent=%s class=%s)",
                ctx.agent_id, ctx.write_class.value,
            )
            return CheckResult.FAIL

        ok = _verify_hmac(mac_payload, mac)
        if not ok:
            LOG.warning(
                "[IBAC:Signature] FAIL — invalid MAC (agent=%s class=%s path=%s)",
                ctx.agent_id, ctx.write_class.value, ctx.target_path,
            )
            return CheckResult.FAIL

        return CheckResult.PASS


# ─────────────────────────────────────────────────────────────────────────────
# Checker 3: ACL — capability policy lookup
# ─────────────────────────────────────────────────────────────────────────────

# Maps WriteClass enum value strings to the CAPABILITY_POLICY action required
_CLASS_TO_ACTION: Dict[str, str] = {
    "DOME_APPEND":     "write_iron_dome",
    "GITOPS_MUTATION": "write_file",
    "GHOST_RECALL":    "write_memory",
}


class ACLChecker:
    """
    Checks the calling agent's capability policy for the required action.

    Loads CAPABILITY_POLICY from ibac_policy (no FastAPI dependency).
    Falls back to allow-all on policy load failure (fail-open on config error,
    so a broken import doesn't silently lock out all writes).
    """

    name = "ACLChecker"

    def _get_policy(self) -> Dict[str, List[str]]:
        try:
            from sovereignnation.ibac_policy import CAPABILITY_POLICY
            return CAPABILITY_POLICY
        except Exception:
            # Fallback: ibac_daemon has the same data (heavier import, but works)
            try:
                from sovereignnation.ibac_daemon import CAPABILITY_POLICY  # type: ignore
                return CAPABILITY_POLICY
            except Exception:
                return {}

    def check(self, ctx: WriteContext) -> CheckResult:
        required_action = _CLASS_TO_ACTION.get(ctx.write_class.value)
        if not required_action:
            LOG.warning("[IBAC:ACL] FAIL — unknown WriteClass: %s", ctx.write_class)
            return CheckResult.FAIL

        policy = self._get_policy()
        if not policy:
            # Policy unavailable — fail-open: don't block writes due to config error
            LOG.warning(
                "[IBAC:ACL] Policy unavailable — allowing agent=%s through (fail-open)",
                ctx.agent_id,
            )
            return CheckResult.PASS

        allowed = policy.get(ctx.agent_id, [])
        if required_action in allowed:
            return CheckResult.PASS

        LOG.warning(
            "[IBAC:ACL] FAIL — agent=%s lacks '%s' (allowed=%s path=%s)",
            ctx.agent_id, required_action, allowed, ctx.target_path,
        )
        return CheckResult.FAIL


# ─────────────────────────────────────────────────────────────────────────────
# QuorumGate
# ─────────────────────────────────────────────────────────────────────────────

class QuorumGate:
    """
    N-of-M parallel macro checker enforcement gate.

    Every write path that imports this gate gets a fence: all checkers run
    concurrently (in async mode), and at least `required_passes` must return
    CheckResult.PASS before the write is allowed.

    On denial: writes an access_denied record to Iron Dome, logs a WARNING,
    and raises PermissionError — callers catch this and return an appropriate
    error to their own callers.

    Thread safety: reentrant.  Each checker uses its own lock or is stateless.
    """

    def __init__(
        self,
        checkers: List[MacroChecker],
        required_passes: int = 2,
        name: str = "QuorumGate",
    ):
        if required_passes < 1 or required_passes > len(checkers):
            raise ValueError(
                f"required_passes={required_passes} must be in [1, {len(checkers)}]"
            )
        self.checkers        = checkers
        self.required_passes = required_passes
        self.name            = name

    # ── Sync path ─────────────────────────────────────────────────────────────

    def enforce(self, ctx: WriteContext) -> None:
        """
        Synchronous enforcement — checkers run sequentially.
        Use from sync callers (e.g. tests, CLI tools).
        For async callers, prefer enforce_async() for parallel execution.
        """
        results: List[CheckResult] = []
        for checker in self.checkers:
            try:
                results.append(checker.check(ctx))
            except Exception as exc:
                LOG.warning(
                    "[%s] Checker %s raised: %s",
                    self.name, getattr(checker, "name", "?"), exc,
                )
                results.append(CheckResult.FAIL)

        passes = sum(1 for r in results if r == CheckResult.PASS)
        self._finalize(ctx, results, passes)

    # ── Async path ────────────────────────────────────────────────────────────

    async def enforce_async(self, ctx: WriteContext) -> None:
        """
        Async enforcement — all checkers run in parallel thread-pool workers.

        Wall-clock ≈ slowest single checker (~0.1 ms for all three combined),
        not the sequential sum.  Safe to await from any async write path.
        """
        async def _run(checker: MacroChecker) -> CheckResult:
            try:
                return await asyncio.to_thread(checker.check, ctx)
            except Exception as exc:
                LOG.warning(
                    "[%s] Checker %s async error: %s",
                    self.name, getattr(checker, "name", "?"), exc,
                )
                return CheckResult.FAIL

        results: List[CheckResult] = list(
            await asyncio.gather(*[_run(c) for c in self.checkers])
        )
        passes = sum(1 for r in results if r == CheckResult.PASS)
        self._finalize(ctx, results, passes)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _finalize(
        self,
        ctx: WriteContext,
        results: List[CheckResult],
        passes: int,
    ) -> None:
        """Log result and raise PermissionError if quorum not met."""
        names  = [getattr(c, "name", f"Checker{i}") for i, c in enumerate(self.checkers)]
        detail = ", ".join(f"{n}={r.value}" for n, r in zip(names, results))

        LOG.debug(
            "[%s] agent=%s class=%s passes=%d/%d need=%d — %s",
            self.name, ctx.agent_id, ctx.write_class.value,
            passes, len(self.checkers), self.required_passes, detail,
        )

        if passes >= self.required_passes:
            return  # allowed

        # ── Denied — audit to Iron Dome then raise ────────────────────────────
        try:
            from memory.iron_dome import dome_write
            dome_write("QuorumGate", "access_denied", {
                "gate":        self.name,
                "agent_id":    ctx.agent_id,
                "proposal_id": ctx.proposal_id,
                "write_class": ctx.write_class.value,
                "target_path": ctx.target_path,
                "passes":      passes,
                "needed":      self.required_passes,
                "results":     {n: r.value for n, r in zip(names, results)},
            })
        except Exception:
            pass  # never let audit logging block the denial

        LOG.warning(
            "[%s] ACCESS DENIED — agent=%s class=%s path=%s "
            "passes=%d/%d need=%d | %s",
            self.name, ctx.agent_id, ctx.write_class.value, ctx.target_path,
            passes, len(self.checkers), self.required_passes, detail,
        )
        raise PermissionError(
            f"{self.name} denied {ctx.agent_id}:{ctx.write_class.value} on "
            f"'{ctx.target_path}' — {passes}/{len(self.checkers)} checkers passed "
            f"(need {self.required_passes}) | {detail}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Pre-built gate instances — import these in callers
# ─────────────────────────────────────────────────────────────────────────────

_CHECKERS: List[MacroChecker] = [
    RateLimitChecker(),   # Checker 0 — in-memory sliding window
    SignatureChecker(),   # Checker 1 — HMAC-SHA256 verify
    ACLChecker(),         # Checker 2 — CAPABILITY_POLICY lookup
]

# ALL 3 must pass — highest-risk path: file writes + git commits
# Caller MUST provide metadata={"mac_payload": ..., "mac": ...}
gitops_gate = QuorumGate(_CHECKERS, required_passes=3, name="GitOpsGate")

# 2 of 3 must pass — memory writes; signature optional (no pre-computed MAC)
# ACL pass + RateLimit pass = quorum met even if SignatureChecker fails
memory_gate = QuorumGate(_CHECKERS, required_passes=2, name="MemoryGate")
