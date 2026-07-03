"""GH05T3 -> gml_kernel (Rust) FFI bridge.

Loads the compiled Rust glyph kernel and calls into it via ctypes.
Kept separate from kernel_adapter.py, which is explicitly Rust-free
(wraps the pure-Python sovereign-core Runtime).
"""
from __future__ import annotations

import asyncio
import ctypes
import json
import os

_REQUIRED_MODEL_CALL_FIELDS = ("backend", "prompt", "version")
_SUPPORTED_MODEL_CALL_VERSIONS = {"v1", "v2"}

_LIB_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "gml_kernel",
    "target",
    "release",
    "libgml_kernel.so",
)

_gml = ctypes.CDLL(_LIB_PATH)

_gml.gh05t3_run_core_loop.restype = ctypes.c_void_p

_gml.gh05t3_model_call.restype = ctypes.c_void_p
_gml.gh05t3_model_call.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p]

_gml.gh05t3_free_string.argtypes = [ctypes.c_void_p]
_gml.gh05t3_free_string.restype = None


def _take_string(raw: int) -> str:
    try:
        return ctypes.cast(raw, ctypes.c_char_p).value.decode("utf-8")
    finally:
        _gml.gh05t3_free_string(raw)


def run_gh05t3_kernel_core() -> str:
    """Runs the whole Rust core loop. MODEL_CALL glyphs resolve to the Rust
    echo-stub (kernel/model.rs / ffi::model_call_summary) — this does NOT
    reach ghost_llm. Rust cannot call back into Python through this ctypes
    binding; that would need an explicit callback registration (a Python
    CFUNCTYPE passed into a Rust static), which is not built yet.
    """
    raw = _gml.gh05t3_run_core_loop()
    return _take_string(raw)


def call_rust_model_stub(backend: str, prompt: str, version: str = "v2") -> str:
    """Direct call into Rust's gh05t3_model_call. Returns the v2 JSON envelope
    (kernel::payload::ModelCallPayload) as a string, e.g.:
      {"backend":"claude","prompt":"...","version":"v2","meta":{}}
    Isolated from the full core loop — useful for testing the FFI contract.
    Feed the result into handle_model_call_json() to actually run it.
    """
    raw = _gml.gh05t3_model_call(
        backend.encode("utf-8"), prompt.encode("utf-8"), version.encode("utf-8")
    )
    return _take_string(raw)


def check_dependencies() -> dict:
    """Real dependency health check — importability only, no network calls."""
    status = {}

    try:
        import backend.ghost_llm  # noqa: F401
        status["ghost_llm"] = True
    except Exception as e:
        status["ghost_llm"] = f"ERROR: {e}"

    try:
        import httpx  # noqa: F401
        status["httpx"] = True
    except Exception as e:
        status["httpx"] = f"ERROR: {e}"

    status["gml_kernel_so"] = os.path.isfile(_LIB_PATH)

    return status


def run_model_via_ghost_llm(backend: str, prompt: str, version: str = "v1") -> str:
    """Routes a MODEL_CALL glyph's prompt through GH05T3's real LLM cascade
    (backend.ghost_llm.chat_once) instead of the Rust echo-stub.

    chat_once has no backend/version selector of its own — it picks a
    provider via internal task classification and the LLM_PROVIDER env var.
    backend/version are accepted here for parity with the glyph schema but
    are not currently forwarded into the cascade.

    Never raises: any failure (missing deps, cascade exhausted, etc.) falls
    back to a literal "[LOCAL_FALLBACK] {prompt}" response so callers always
    get a string back.

    Uses asyncio.run, so call this from sync code only. If the caller is
    already inside an event loop (e.g. a FastAPI handler), await
    chat_once(...) directly instead.
    """
    try:
        from backend.ghost_llm import chat_once  # deferred: pulls in httpx et al.

        text, _provider_used = asyncio.run(
            chat_once(session="gml_kernel", system="", user=prompt)
        )
        return text
    except Exception:
        return f"[LOCAL_FALLBACK] {prompt}"


def handle_model_call_json(payload_json: str) -> str:
    """v2 MODEL_CALL contract: JSON in, JSON out.

    Input shape (matches Rust's kernel::payload::ModelCallPayload):
      {"backend": str, "prompt": str, "version": str, "meta": {...}}

    Output shape:
      {"backend": str|None, "version": str|None, "provider_used": str|None,
       "text": str|None, "error": str|None}

    Never raises. Missing/invalid fields and cascade failures both come back
    as a structured envelope rather than an exception.
    """
    try:
        payload = json.loads(payload_json)
    except json.JSONDecodeError as e:
        return json.dumps({
            "error": f"invalid JSON: {e}",
            "backend": None, "version": None, "provider_used": None, "text": None,
        })

    missing = [f for f in _REQUIRED_MODEL_CALL_FIELDS if f not in payload]
    if missing:
        return json.dumps({
            "error": f"missing field(s): {', '.join(missing)}",
            "backend": payload.get("backend"),
            "version": payload.get("version"),
            "provider_used": None,
            "text": None,
        })

    backend = payload["backend"]
    prompt = payload["prompt"]
    version = payload["version"]

    if version not in _SUPPORTED_MODEL_CALL_VERSIONS:
        return json.dumps({
            "error": f"unsupported version: {version}",
            "backend": backend, "version": version,
            "provider_used": None, "text": None,
        })

    try:
        from backend.ghost_llm import chat_once  # deferred: pulls in httpx et al.

        text, provider_used = asyncio.run(
            chat_once(session="gml_kernel", system="", user=prompt)
        )
        return json.dumps({
            "backend": backend, "version": version,
            "provider_used": provider_used, "text": text, "error": None,
        })
    except Exception as e:
        return json.dumps({
            "backend": backend, "version": version,
            "provider_used": None,
            "text": f"[LOCAL_FALLBACK] {prompt}",
            "error": str(e),
        })
