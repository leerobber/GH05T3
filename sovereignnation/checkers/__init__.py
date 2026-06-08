"""
sovereignnation.checkers — PolicyStore-backed MacroChecker implementations
===========================================================================
These checkers use per-agent JSON policy files (loaded via PolicyStore)
instead of the flat CAPABILITY_POLICY dict in access_control.py.

Import convenience:
    from sovereignnation.checkers import (
        PolicyACLChecker, PolicyRateLimitChecker, SignatureChecker,
        make_gitops_gate, make_memory_gate,
    )
"""
from .acl_checker        import PolicyACLChecker
from .rate_limit_checker import PolicyRateLimitChecker
from .signature_checker  import SignatureChecker

from sovereignnation.access_control import QuorumGate
from sovereignnation.policy_store   import policy_store as _default_store


def make_gitops_gate(store=None, required_passes: int = 3) -> QuorumGate:
    """
    Build the 3-of-3 GitOps gate using PolicyStore-backed checkers.
    All three checkers must pass before any file write + git commit proceeds.
    """
    ps = store or _default_store
    return QuorumGate(
        [PolicyRateLimitChecker(ps), SignatureChecker(), PolicyACLChecker(ps)],
        required_passes=required_passes,
        name="PolicyGitOpsGate",
    )


def make_memory_gate(store=None, required_passes: int = 2) -> QuorumGate:
    """
    Build the 2-of-3 memory gate using PolicyStore-backed checkers.
    Signature is optional (no pre-computed MAC on memory writes typically).
    """
    ps = store or _default_store
    return QuorumGate(
        [PolicyRateLimitChecker(ps), SignatureChecker(), PolicyACLChecker(ps)],
        required_passes=required_passes,
        name="PolicyMemoryGate",
    )


__all__ = [
    "PolicyACLChecker",
    "PolicyRateLimitChecker",
    "SignatureChecker",
    "make_gitops_gate",
    "make_memory_gate",
]
