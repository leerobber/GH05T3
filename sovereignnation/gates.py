"""
Gate registry — canonical QuorumGate instances for all write paths
==================================================================
Single import point for every write-path caller.  Avoids each caller
having to decide which gate tier to use.

Two tiers:
  basic_*_gate  — flat CAPABILITY_POLICY dict (access_control.py), no file I/O,
                  ~0.01 ms.  Used as fallback if policies/ dir is missing.

  policy_*_gate — per-agent JSON policies (sovereignnation/policies/),
                  path-rule ACL + PolicyStore rate limits.  This is the
                  default for all production write paths.

Public aliases (these are what callers should import):
  gitops_gate   → policy_gitops_gate (required_passes=3)
  memory_gate   → policy_memory_gate (required_passes=2)

Why dome_write is NOT gated here:
  Iron Dome is the audit trail.  QuorumGate._finalize() calls dome_write()
  to record every denial.  If dome_write were itself gated, a denied write
  would trigger a nested dome_write call → denial → dome_write ... (recursive
  until stack overflow).  The audit trail must always succeed.  Gate the
  callers (GitOpsMutator, GhostRecall, SAGE), not the ledger itself.

Usage:
    from sovereignnation.gates import WriteClass, WriteContext, gitops_gate, memory_gate
"""
from __future__ import annotations

import logging

LOG = logging.getLogger("aethyro.gates")

# ── Basic (flat-dict) gates ───────────────────────────────────────────────────
# Import the pre-built instances from access_control — no file I/O required.
from sovereignnation.access_control import (  # noqa: E402
    WriteClass,
    WriteContext,
    CheckResult,
    QuorumGate,
    gitops_gate  as basic_gitops_gate,
    memory_gate  as basic_memory_gate,
)

# ── PolicyStore-backed gates ──────────────────────────────────────────────────
# Built from per-agent JSON files in sovereignnation/policies/.
# Falls back to basic gates if the policies directory doesn't exist yet.
try:
    from sovereignnation.checkers import make_gitops_gate, make_memory_gate

    policy_gitops_gate: QuorumGate = make_gitops_gate()
    policy_memory_gate: QuorumGate = make_memory_gate()
    LOG.debug("[Gates] PolicyStore gates ready (%s, %s)",
              policy_gitops_gate.name, policy_memory_gate.name)
except Exception as _err:
    LOG.warning(
        "[Gates] PolicyStore gates unavailable (%s) — falling back to basic gates",
        _err,
    )
    policy_gitops_gate = basic_gitops_gate
    policy_memory_gate = basic_memory_gate

# ── Production aliases — callers should import these ─────────────────────────
gitops_gate: QuorumGate = policy_gitops_gate   # all 3 must pass (file write + git)
memory_gate: QuorumGate = policy_memory_gate   # 2 of 3 must pass (memory write)

__all__ = [
    "WriteClass",
    "WriteContext",
    "CheckResult",
    "QuorumGate",
    "gitops_gate",
    "memory_gate",
    "basic_gitops_gate",
    "basic_memory_gate",
    "policy_gitops_gate",
    "policy_memory_gate",
]
