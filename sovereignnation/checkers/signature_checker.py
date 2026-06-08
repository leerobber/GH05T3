"""
SignatureChecker — HMAC-SHA256 / IBAC capability token verifier
===============================================================
Verifies that the write context carries a valid cryptographic credential.
Importable from the checkers/ package for composition with PolicyStore-backed
ACL and rate-limit checkers.

Two validation paths (checked in order):

  Path 1 — IBAC capability token (preferred):
    ctx.metadata["capability"] = {
        "token":    "ibac:SAGE1234:abcdef1234567890",
        "action":   "write_file",
        "resource": "kairos/sage_loop.py",
    }
    Validated against the shared master key using the same 1-minute-window
    HMAC that ibac_daemon._verify_token() uses.  The token encodes
    (agent_id, action, resource, minute_ts) — one token per write attempt.

  Path 2 — raw HMAC mac_payload / mac:
    ctx.metadata["mac_payload"] = str  — string that was signed
    ctx.metadata["mac"]         = str  — full 64-hex HMAC-SHA256 digest
    Used by GitOpsMutator for its own mutation-integrity signing.

Priority: if capability is present, validate it and do NOT fall through to
  the mac check. This prevents a caller from bypassing a bad capability by
  also providing a valid HMAC.

Behaviour matrix:
  No metadata at all + no key on disk  → PASS  (dev mode)
  No metadata at all + key exists      → FAIL  (credentials required)
  capability present + valid token     → PASS
  capability present + invalid token   → FAIL  (no fallthrough)
  mac_payload+mac present + valid      → PASS
  mac_payload+mac present + invalid    → FAIL

For memory_gate (required_passes=2): one FAIL here is tolerable if
  PolicyACLChecker + PolicyRateLimitChecker both pass.
For gitops_gate (required_passes=3): ALL must pass, so callers MUST
  provide either a valid capability token or a valid HMAC mac pair.

The master key file is shared with gitops_mutator, ibac_daemon, and
capability_client:
  kairos/data/gitops_master.key
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional

from sovereignnation.access_control import CheckResult, WriteContext

LOG = logging.getLogger("aethyro.checkers.signature")

_KEY_PATH = Path(__file__).parent.parent.parent / "kairos" / "data" / "gitops_master.key"


def _load_key() -> Optional[bytes]:
    if _KEY_PATH.exists():
        try:
            return bytes.fromhex(_KEY_PATH.read_text().strip())
        except Exception:
            pass
    return None


def _verify_hmac(data: str, signature: str) -> bool:
    """Constant-time HMAC-SHA256 verify. Returns True in dev mode (no key)."""
    key = _load_key()
    if not key:
        return True
    expected = hmac.new(key, data.encode("utf-8"), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def _verify_ibac_token(token: str, agent_id: str, action: str, resource: str) -> bool:
    """
    Validate an IBAC capability token.

    Mirrors ibac_daemon._verify_token() exactly — same key, same payload
    format, same 1-minute sliding window.  Runs in-process so no network
    call is needed during gate enforcement.

    Returns True in dev mode (no key on disk).
    """
    key = _load_key()
    if not key:
        return True   # dev mode — no key means open
    now = int(time.time() // 60)
    for ts in [now, now - 1]:   # 1-minute grace window (matches daemon)
        payload  = f"{agent_id}|{action}|{resource}|{ts}"
        sig      = hmac.new(key, payload.encode(), hashlib.sha256).hexdigest()[:16]
        expected = f"ibac:{agent_id[:8]}:{sig}"
        if hmac.compare_digest(token, expected):
            return True
    return False


class SignatureChecker:
    """
    Credential verifier supporting two formats:
      - IBAC capability token  (ctx.metadata["capability"])
      - Raw HMAC mac pair      (ctx.metadata["mac_payload"] + ctx.metadata["mac"])

    See module docstring for the full behaviour matrix.
    """

    name = "SignatureChecker"

    def check(self, ctx: WriteContext) -> CheckResult:
        key_exists = _KEY_PATH.exists()

        # ── Path 1: IBAC capability token ─────────────────────────────────
        cap = ctx.metadata.get("capability")
        if cap and isinstance(cap, dict):
            token    = cap.get("token", "")
            action   = cap.get("action", "")
            resource = cap.get("resource", ctx.target_path)

            if _verify_ibac_token(token, ctx.agent_id, action, resource):
                LOG.debug(
                    "[Sig] PASS — valid IBAC token (agent=%s action=%s)",
                    ctx.agent_id, action,
                )
                return CheckResult.PASS

            LOG.warning(
                "[Sig] FAIL — invalid IBAC capability token "
                "(agent=%s action=%s resource=%s)",
                ctx.agent_id, action, resource,
            )
            return CheckResult.FAIL   # no fallthrough — explicit credential, explicit verdict

        # ── Path 2: raw HMAC mac_payload + mac ────────────────────────────
        mac_payload = ctx.metadata.get("mac_payload")
        mac         = ctx.metadata.get("mac")

        if not mac_payload or not mac:
            if not key_exists:
                return CheckResult.PASS  # dev mode — no key means open
            LOG.debug(
                "[Sig] FAIL — no credential in metadata (agent=%s class=%s)",
                ctx.agent_id, ctx.write_class.value,
            )
            return CheckResult.FAIL

        ok = _verify_hmac(mac_payload, mac)
        if not ok:
            LOG.warning(
                "[Sig] FAIL — invalid HMAC (agent=%s class=%s path=%s)",
                ctx.agent_id, ctx.write_class.value, ctx.target_path,
            )
            return CheckResult.FAIL

        LOG.debug(
            "[Sig] PASS — valid HMAC (agent=%s class=%s)",
            ctx.agent_id, ctx.write_class.value,
        )
        return CheckResult.PASS
