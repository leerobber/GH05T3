"""
PolicyACLChecker — PolicyStore-backed Access Control List checker
=================================================================
Checks two things from the agent's JSON policy:

  1. WriteClass whitelist — is the write class listed in allowed_write_classes?
  2. Path rules — does any path rule explicitly permit this write class on
     the given target_path?

Path rule matching:
  "prefix": "*"       → matches any target_path (global catch-all)
  "prefix": "memory/" → matches any path starting with "memory/"
  "prefix": ""        → skipped (falsy guard, not a valid prefix)

Allow flags per rule:
  allow_gitops: bool   — permits WriteClass.GITOPS_MUTATION
  allow_dome:   bool   — permits WriteClass.DOME_APPEND
  allow_ghost:  bool   — permits WriteClass.GHOST_RECALL

Decision matrix:
  1. No policy found for agent_id           → FAIL
  2. write_class not in allowed_write_classes → FAIL
  3. path_rules empty                       → FAIL (explicit allow required)
  4. No path rule prefix matches target     → FAIL
  5. Matching rule found — allow flag True  → PASS
  6. Matching rule found — allow flag False → FAIL
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sovereignnation.access_control import CheckResult, WriteClass, WriteContext

if TYPE_CHECKING:
    from sovereignnation.policy_store import PolicyStore

LOG = logging.getLogger("aethyro.checkers.acl")

# Maps WriteClass to the allow_* key in path_rules
_CLASS_ALLOW_KEY = {
    WriteClass.GITOPS_MUTATION: "allow_gitops",
    WriteClass.GHOST_RECALL:    "allow_ghost",
    WriteClass.DOME_APPEND:     "allow_dome",
}


class PolicyACLChecker:
    """
    PolicyStore-backed ACL checker.

    Replaces the flat CAPABILITY_POLICY lookup with per-agent JSON policies
    that support fine-grained path rules and write-class whitelists.
    """

    name = "PolicyACLChecker"

    def __init__(self, policy_store: "PolicyStore"):
        self.policy_store = policy_store

    def check(self, ctx: WriteContext) -> CheckResult:
        policy = self.policy_store.get_policy(ctx.agent_id)
        if not policy:
            LOG.warning(
                "[ACL] FAIL — no policy file for agent=%s", ctx.agent_id
            )
            return CheckResult.FAIL

        # ── 1. WriteClass whitelist ────────────────────────────────────────────
        allowed_classes = policy.get("allowed_write_classes", [])
        if ctx.write_class.value not in allowed_classes:
            LOG.warning(
                "[ACL] FAIL — agent=%s class=%s not in allowed_write_classes=%s",
                ctx.agent_id, ctx.write_class.value, allowed_classes,
            )
            return CheckResult.FAIL

        # ── 2. Path rules ──────────────────────────────────────────────────────
        path_rules = policy.get("path_rules", [])
        if not path_rules:
            LOG.warning(
                "[ACL] FAIL — agent=%s has no path_rules (explicit allow required)",
                ctx.agent_id,
            )
            return CheckResult.FAIL

        allow_key = _CLASS_ALLOW_KEY.get(ctx.write_class)
        if allow_key is None:
            LOG.warning("[ACL] FAIL — unknown WriteClass: %s", ctx.write_class)
            return CheckResult.FAIL

        for rule in path_rules:
            prefix = rule.get("prefix", "")
            # "*" is a wildcard matching everything; otherwise prefix must be truthy
            # and ctx.target_path must start with it.
            if prefix == "*" or (prefix and ctx.target_path.startswith(prefix)):
                if rule.get(allow_key, False):
                    LOG.debug(
                        "[ACL] PASS — agent=%s class=%s path=%s matched rule prefix=%s",
                        ctx.agent_id, ctx.write_class.value, ctx.target_path, prefix,
                    )
                    return CheckResult.PASS
                else:
                    LOG.warning(
                        "[ACL] FAIL — agent=%s class=%s path=%s matched rule prefix=%s "
                        "but %s=false",
                        ctx.agent_id, ctx.write_class.value, ctx.target_path,
                        prefix, allow_key,
                    )
                    return CheckResult.FAIL

        LOG.warning(
            "[ACL] FAIL — agent=%s class=%s path=%s matched no path rules (rules=%d)",
            ctx.agent_id, ctx.write_class.value, ctx.target_path, len(path_rules),
        )
        return CheckResult.FAIL
