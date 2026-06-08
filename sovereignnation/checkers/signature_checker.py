"""
SignatureChecker — HMAC-SHA256 capability token verifier
=========================================================
Verifies that the write context carries a valid HMAC-SHA256 signature.
Identical logic to the SignatureChecker in access_control.py but factored
into the checkers/ package so it can be composed with PolicyStore-backed
ACL and rate-limit checkers.

Reads from ctx.metadata:
  "mac_payload": str  — the string that was signed by the caller
  "mac":         str  — the full 64-hex HMAC-SHA256 digest

Behaviour matrix:
  Key absent on disk + no MAC in ctx   → PASS  (dev mode)
  Key present  + no MAC in ctx         → FAIL  (MAC required but missing)
  Key present  + wrong MAC             → FAIL  (tampered / wrong key)
  Key present  + correct MAC           → PASS

For memory_gate (required_passes=2): one FAIL here is tolerable if
  PolicyACLChecker + PolicyRateLimitChecker both pass.
For gitops_gate (required_passes=3): ALL must pass, so callers MUST
  populate ctx.metadata["mac_payload"] and ctx.metadata["mac"].

The master key file is shared with gitops_mutator and ibac_daemon:
  kairos/data/gitops_master.key
"""
from __future__ import annotations

import hashlib
import hmac
import logging
from pathlib import Path
from typing import Optional

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


class SignatureChecker:
    """
    HMAC-SHA256 signature verifier.

    Same semantics as sovereignnation.access_control.SignatureChecker but
    importable from the checkers/ package alongside PolicyACLChecker and
    PolicyRateLimitChecker.
    """

    name = "SignatureChecker"

    def check(self, ctx: WriteContext) -> CheckResult:
        mac_payload = ctx.metadata.get("mac_payload")
        mac         = ctx.metadata.get("mac")
        key_exists  = _KEY_PATH.exists()

        if not mac_payload or not mac:
            if not key_exists:
                return CheckResult.PASS  # dev mode — no key means open
            LOG.debug(
                "[Sig] FAIL — no MAC in metadata (agent=%s class=%s)",
                ctx.agent_id, ctx.write_class.value,
            )
            return CheckResult.FAIL

        ok = _verify_hmac(mac_payload, mac)
        if not ok:
            LOG.warning(
                "[Sig] FAIL — invalid MAC (agent=%s class=%s path=%s)",
                ctx.agent_id, ctx.write_class.value, ctx.target_path,
            )
            return CheckResult.FAIL

        return CheckResult.PASS
