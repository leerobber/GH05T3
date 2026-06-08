"""
IBAC Policy — Canonical Capability Policy & Protected Path List
================================================================
Single source of truth for what each agent role is allowed to do.
Imported by both ibac_daemon.py (network enforcement) and
access_control.py (in-process macro checker enforcement).

Keeping policy here prevents the two enforcement layers from drifting.
"""
from __future__ import annotations

from typing import Dict, List

# ── Capability Policy ─────────────────────────────────────────────────────────
# Maps agent_id → list of allowed action strings.
# Actions NOT listed here are denied by default (deny-by-default model).

CAPABILITY_POLICY: Dict[str, List[str]] = {
    "avery-sovereign": [
        "read_memory", "write_belief", "plan_strategy", "emit_swarm_message",
    ],
    "forge-sovereign": [
        "read_memory", "write_file", "run_python_sandbox", "git_commit",
        "emit_swarm_message",
    ],
    "oracle-sovereign": [
        "read_memory", "read_file", "semantic_search", "emit_swarm_message",
    ],
    "sentinel-sovereign": [
        "read_memory", "read_file", "audit_code", "block_agent",
        "emit_swarm_message", "write_iron_dome",
    ],
    "nexus-sovereign": [
        "read_memory", "route_task", "emit_swarm_message",
        "propagate_update", "git_commit",
    ],
    "codex-sovereign": [
        "read_memory", "read_file", "write_file", "emit_swarm_message",
    ],
    # ── Internal system actors ────────────────────────────────────────────────
    "SAGE": [
        "read_memory", "write_memory", "read_file", "write_file", "git_commit",
        "emit_swarm_message", "write_iron_dome", "run_python_sandbox", "write_belief",
    ],
    "GitOpsMutator": [
        "write_file", "git_commit", "write_iron_dome",
    ],
    "GhostRecall": [
        "write_memory", "write_iron_dome", "read_file",
    ],
    "TriageGovernor": [
        "write_memory", "write_iron_dome", "read_memory",
    ],
    "MetaAgent": [
        "write_iron_dome", "read_file",
    ],
    "system": [
        "read_memory", "read_file", "emit_swarm_message",
    ],
}

# ── Protected Paths ───────────────────────────────────────────────────────────
# No agent may write to these paths via the GitOps pipeline.
# (SAGE with explicit override is the only exception handled in gitops_mutator.)

PROTECTED_PATHS: List[str] = [
    "kairos/gitops_mutator.py",
    "kairos/verification.py",
    "memory/iron_dome.py",
    ".env",
    "supervisor.py",
    "START_ALL.bat",
    "sovereignnation/ibac_daemon.py",
    "sovereignnation/access_control.py",
    "sovereignnation/ibac_policy.py",
]

# ── WriteClass → required action ─────────────────────────────────────────────
# Maps access_control.WriteClass enum values to CAPABILITY_POLICY action strings.
# Used by ACLChecker without importing WriteClass (avoids circular deps).

WRITE_CLASS_ACTIONS: Dict[str, str] = {
    "DOME_APPEND":      "write_iron_dome",
    "GITOPS_MUTATION":  "write_file",
    "GHOST_RECALL":     "write_memory",
}
