"""
PolicyStore — File-based per-agent policy loader with global defaults
======================================================================
Loads per-agent capability policies from JSON files in the `policies/`
directory and merges them with global defaults.

Policy files:
  policies/_global.json          — global defaults (applies to all agents)
  policies/<agent_id>.json       — per-agent overrides

Merge rules (precedence: per-agent > global):
  allowed_write_classes: per-agent value replaces global default
  path_rules:            global default_path_rules PREPEND per-agent path_rules
                         (global guards run first — agent cannot override them)
  rate_limits:           per-agent dict UPDATES global default (per-key override)

Path rule matching in ACLChecker:
  prefix="*"     → matches any target_path (wildcard catch-all)
  prefix="foo/"  → matches target_paths that start with "foo/"
  prefix=""      → treated as no match (falsy guard)

JSON schema per agent file:
    {
        "agent_id":             "SAGE",
        "description":          "...",
        "allowed_write_classes": ["GITOPS_MUTATION", "GHOST_RECALL", "DOME_APPEND"],
        "path_rules": [
            {
                "prefix":       "*",
                "allow_gitops": true,
                "allow_dome":   true,
                "allow_ghost":  true,
                "comment":      "optional human note"
            }
        ],
        "rate_limits": {
            "GITOPS_MUTATION": {"max_per_minute": 15},
            "GHOST_RECALL":    {"max_per_minute": 200},
            "DOME_APPEND":     {"max_per_minute": 500}
        }
    }

Usage:
    from sovereignnation.policy_store import PolicyStore

    ps = PolicyStore("sovereignnation/policies")
    policy = ps.get_policy("SAGE")
    # {"agent_id": "SAGE", "allowed_write_classes": [...], "path_rules": [...], ...}

    ps.reload()           # clear full cache (e.g. after a policy file edit)
    ps.reload("SAGE")     # clear only SAGE policy cache entry
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

LOG = logging.getLogger("aethyro.policy_store")

# Default global policy returned when _global.json is absent
_EMPTY_GLOBAL: Dict[str, Any] = {
    "default_allowed_write_classes": [],
    "default_path_rules":            [],
    "default_rate_limits": {
        "GITOPS_MUTATION": {"max_per_minute": 10},
        "GHOST_RECALL":    {"max_per_minute": 100},
        "DOME_APPEND":     {"max_per_minute": 500},
    },
}


class PolicyStore:
    """
    Loads per-agent policies from JSON files with global defaults.

    Thread safety: _cache reads/writes are not locked — this is intentional.
    Worst case: two threads both miss the cache and both load the same file.
    The file load is idempotent and the result is deterministic, so a race
    just means two redundant reads.  No corruption possible.
    """

    def __init__(self, policy_dir: str):
        """
        Args:
            policy_dir: Path to the directory containing policy JSON files.
                        Can be absolute or relative to CWD.
        """
        self.policy_dir    = Path(policy_dir).resolve()
        self._cache:        Dict[str, Dict[str, Any]] = {}
        self._global_policy = self._load_global()

    # ── Public API ────────────────────────────────────────────────────────────

    def get_policy(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """
        Return the merged policy for `agent_id`, or None if no policy file
        exists for this agent.

        The returned dict always has these keys:
          agent_id, description, allowed_write_classes, path_rules, rate_limits
        """
        return self.load_policy(agent_id)

    def reload(self, agent_id: str | None = None) -> None:
        """
        Invalidate the policy cache.

        Args:
            agent_id: If provided, evict only this agent's entry.
                      If None (default), clear the entire cache and reload
                      the global policy from disk.
        """
        if agent_id is not None:
            self._cache.pop(agent_id, None)
            LOG.debug("[PolicyStore] Cache cleared for agent=%s", agent_id)
        else:
            self._cache.clear()
            self._global_policy = self._load_global()
            LOG.info("[PolicyStore] Full cache cleared — global policy reloaded")

    def list_agents(self) -> List[str]:
        """Return agent IDs that have explicit policy files (excludes _global)."""
        agents = []
        for p in self.policy_dir.glob("*.json"):
            if p.stem != "_global":
                agents.append(p.stem)
        return sorted(agents)

    # ── Internal ──────────────────────────────────────────────────────────────

    def load_policy(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Load (and cache) the merged policy for `agent_id`."""
        if agent_id in self._cache:
            return self._cache[agent_id]

        path = self.policy_dir / f"{agent_id}.json"
        if not path.exists():
            LOG.debug("[PolicyStore] No policy file for agent=%s (%s)", agent_id, path)
            return None

        try:
            with path.open("r", encoding="utf-8") as f:
                agent_policy = json.load(f)
        except Exception as e:
            LOG.error("[PolicyStore] Failed to load policy %s: %s", path, e)
            return None

        merged = self._merge(agent_policy)
        self._cache[agent_id] = merged
        LOG.debug(
            "[PolicyStore] Loaded policy for agent=%s "
            "write_classes=%s rules=%d",
            agent_id,
            merged.get("allowed_write_classes", []),
            len(merged.get("path_rules", [])),
        )
        return merged

    def _load_global(self) -> Dict[str, Any]:
        path = self.policy_dir / "_global.json"
        if not path.exists():
            LOG.debug("[PolicyStore] No _global.json — using empty defaults")
            return dict(_EMPTY_GLOBAL)
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            LOG.debug("[PolicyStore] Loaded _global.json")
            return data
        except Exception as e:
            LOG.error("[PolicyStore] Failed to load _global.json: %s", e)
            return dict(_EMPTY_GLOBAL)

    def _merge(self, agent_policy: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge global defaults with per-agent policy.

        Merge rules:
          allowed_write_classes: agent value wins (or global default)
          path_rules:            global prepend + agent append
          rate_limits:           global defaults, per-agent keys override
        """
        gp = self._global_policy

        allowed = agent_policy.get(
            "allowed_write_classes",
            gp.get("default_allowed_write_classes", []),
        )

        # Global path rules run FIRST (they are hard guards that cannot be
        # bypassed by per-agent rules).  Per-agent rules are appended after.
        path_rules = (
            list(gp.get("default_path_rules", []))
            + list(agent_policy.get("path_rules", []))
        )

        # Per-agent rate limits OVERRIDE global defaults key-by-key
        rate_limits: Dict[str, Any] = dict(gp.get("default_rate_limits", {}))
        for cls, limits in agent_policy.get("rate_limits", {}).items():
            rate_limits[cls] = {**rate_limits.get(cls, {}), **limits}

        return {
            "agent_id":             agent_policy.get("agent_id", ""),
            "description":          agent_policy.get("description", ""),
            "allowed_write_classes": allowed,
            "path_rules":           path_rules,
            "rate_limits":          rate_limits,
        }


# ── Module-level singleton ────────────────────────────────────────────────────
# Callers can import this directly or instantiate their own.

_DEFAULT_POLICY_DIR = Path(__file__).parent / "policies"
policy_store = PolicyStore(str(_DEFAULT_POLICY_DIR))
