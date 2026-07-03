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
import tempfile
import time

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


def check_fs(base_path: str | None = None) -> dict:
    """Filesystem sentinel: verifies we can read/write/delete in a target
    directory. Defaults to the GH05T3 repo root (two levels up from here)."""
    if base_path is None:
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

    result: dict = {"ok": False, "path": base_path, "details": ""}

    try:
        if not os.path.isdir(base_path):
            result["details"] = "base_path is not a directory"
            return result

        fd, tmp_path = tempfile.mkstemp(prefix="gh05t3_fs_sentinel_", dir=base_path)
        os.close(fd)

        payload = b"gh05t3-fs-sentinel"
        with open(tmp_path, "wb") as f:
            f.write(payload)

        with open(tmp_path, "rb") as f:
            data = f.read()

        os.remove(tmp_path)

        if data == payload:
            result["ok"] = True
            result["details"] = "rw ok"
        else:
            result["details"] = "payload mismatch"

    except Exception as e:
        result["details"] = f"exception: {e!r}"

    return result


def check_net(test_url: str = "https://example.com", timeout: float = 2.0) -> dict:
    """Network sentinel: verifies outbound HTTP and basic reachability.
    Uses httpx if available; reports explicitly if httpx is missing."""
    result: dict = {"ok": False, "url": test_url, "details": "", "latency_ms": None}

    try:
        import httpx
    except Exception as e:
        result["details"] = f"httpx missing or unusable: {e!r}"
        return result

    try:
        start = time.perf_counter()
        resp = httpx.get(test_url, timeout=timeout)
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        result["latency_ms"] = int(elapsed_ms)

        if 200 <= resp.status_code < 400:
            result["ok"] = True
            result["details"] = f"reachable, status={resp.status_code}"
        else:
            result["details"] = f"unhealthy status={resp.status_code}"

    except Exception as e:
        result["details"] = f"exception during request: {e!r}"

    return result


def check_dependencies() -> dict:
    """Aggregated dependency health report for GH05T3.

    Returns fs/net/ghost_llm health, plus gml_kernel_so (whether the Rust
    shared lib this module loads is present) for continuity with the
    earlier importability-only version of this check.
    """
    status: dict = {}

    status["fs"] = check_fs()
    status["net"] = check_net()

    try:
        import backend.ghost_llm  # noqa: F401
        status["ghost_llm"] = {"ok": True, "details": "import ok"}
    except Exception as e:
        status["ghost_llm"] = {"ok": False, "details": f"import failed: {e!r}"}

    status["gml_kernel_so"] = os.path.isfile(_LIB_PATH)

    return status


def print_dependency_report() -> None:
    report = check_dependencies()
    print("=== GH05T3 Dependency Report ===")
    print(json.dumps(report, indent=2, sort_keys=True))


def run_model_via_ghost_llm(backend: str, prompt: str, version: str = "v1") -> str:
    """Routes a MODEL_CALL glyph's prompt through GH05T3's real LLM cascade
    (backend.ghost_llm.chat_once) instead of the Rust echo-stub.

    chat_once has no backend/version selector of its own — it picks a
    provider via internal task classification and the LLM_PROVIDER env var.
    backend/version are accepted here for parity with the glyph schema but
    are not currently forwarded into the cascade.

    Checks check_dependencies() first: if ghost_llm isn't importable or
    outbound net is down, skips straight to LOCAL_FALLBACK rather than
    attempting (and waiting out) a call that can't succeed. If the
    pre-check passes but the cascade itself still throws, returns a
    MODEL_ERROR instead of silently falling back, since that's a real,
    unexpected failure rather than a known-bad environment.

    Uses asyncio.run, so call this from sync code only. If the caller is
    already inside an event loop (e.g. a FastAPI handler), await
    chat_once(...) directly instead.
    """
    deps = check_dependencies()
    ghost_ok = deps.get("ghost_llm", {}).get("ok", False)
    net_ok = deps.get("net", {}).get("ok", False)

    if not ghost_ok or not net_ok:
        return f"[LOCAL_FALLBACK] backend={backend},version={version},prompt={prompt}"

    from backend.ghost_llm import chat_once  # deferred: pulls in httpx et al.

    try:
        text, _provider_used = asyncio.run(
            chat_once(session="gml_kernel", system="", user=prompt)
        )
        return text
    except Exception as e:
        return f"[MODEL_ERROR] ghost_llm failure: {e!r}; prompt={prompt}"


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
