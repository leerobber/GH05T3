# phi_service.py — Phi-3.5-mini inference service via onnxruntime-genai (CUDA EP)
# Port: 8112
# Interpreter: C:/Users/leer4/phi_dml_env/Scripts/python.exe
#
# Model: Phi-3.5-mini-Instruct GPU int4-AWQ (RTX 5050 CUDA EP)
#   Load time: ~7s once | Inference: ~95 tok/s on RTX 5050
#   GPU model: ..\RyzenAI-SW\models\phi-3.5-mini-cpu-int4\gpu\gpu-int4-awq-block-128
#   CPU fallback: ..\RyzenAI-SW\models\phi-3.5-mini-cpu-int4\cpu_and_mobile\...
#
# Endpoints:
#   GET  /health -> {status, ready, load_time_s, backend}
#   POST /chat   -> {query, system?, max_tokens?, temperature?}
#             <- {response, tokens_generated, latency_ms, tok_per_sec, model}

from __future__ import annotations
import asyncio
import json
import logging
import os
import time
from typing import Optional

# ── Preload CUDA / cuDNN DLLs from the nvidia-*-cu12 pip packages ─────────────
# onnxruntime loads its CUDA provider DLL with Windows search flags that ignore
# both PATH and os.add_dll_directory(), so the provider's transitive dependency
# resolution can't find the pip-packaged cublasLt64_12.dll, cudnn, etc. The
# supported fix (ORT >= 1.21) is ort.preload_dlls(), which loads those libraries
# into the process up front. MUST run before onnxruntime_genai is imported.
import onnxruntime as _ort  # noqa: E402

_preload_msg = ""
try:
    _ort.preload_dlls(cuda=True, cudnn=True, msvc=True)
    _preload_msg = "ort.preload_dlls() ok"
except Exception as _exc:  # pragma: no cover — surfaces in /health if load fails
    _preload_msg = f"ort.preload_dlls() failed: {_exc}"

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

PHI_MODEL_PATH = (
    r"C:\Users\leer4\RyzenAI-SW\models\phi-3.5-mini-cpu-int4"
    r"\gpu\gpu-int4-awq-block-128"
)

# Special tokens produced by Phi-3.5 that should not appear in API responses
PHI_EOS_TOKENS = ["<|end|>", "<|endoftext|>", "<|assistant|>", "<|user|>", "<|system|>"]

DEFAULT_MAX_TOKENS = 512
DEFAULT_TEMPERATURE = 0.7

log = logging.getLogger("phi_service")
logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-7s  %(message)s")

app = FastAPI(title="Phi-3.5-mini Service", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

_model = None
_tokenizer = None
_lock: Optional[asyncio.Lock] = None
_ready = False
_load_time_s: float = 0.0
_load_error: str = ""
_backend: str = ""


def _load_model() -> None:
    global _model, _tokenizer, _ready, _load_time_s, _load_error, _backend
    try:
        log.info("CUDA DLL preload: %s", _preload_msg)
        import onnxruntime_genai as og
        log.info("Loading Phi-3.5-mini (CUDA EP) from %s ...", PHI_MODEL_PATH)
        t0 = time.perf_counter()
        config = og.Config(PHI_MODEL_PATH)
        config.clear_providers()
        config.append_provider("cuda")
        _model = og.Model(config)
        _tokenizer = og.Tokenizer(_model)
        _load_time_s = round(time.perf_counter() - t0, 2)
        _backend = "cuda"
        _ready = True
        log.info("Phi-3.5-mini ready (CUDA EP) in %.1fs", _load_time_s)
    except Exception as exc:
        _load_error = str(exc)
        log.error("Phi model load failed: %s", exc)


def _generate_sync(system: str, query: str, max_tokens: int, temperature: float) -> tuple:
    """Blocking generation — runs in thread pool executor."""
    import onnxruntime_genai as og

    messages: list[dict] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": query})

    messages_json = json.dumps(messages)
    prompt = _tokenizer.apply_chat_template(messages=messages_json, add_generation_prompt=True)
    input_tokens = _tokenizer.encode(prompt)

    params = og.GeneratorParams(_model)
    params.set_search_options(
        max_length=len(input_tokens) + max_tokens,
        temperature=temperature,
        do_sample=temperature > 0.01,
        top_p=0.9,
        repetition_penalty=1.1,
    )

    generator = og.Generator(_model, params)
    generator.append_tokens(input_tokens)

    t0 = time.perf_counter()
    out_tokens: list = []
    while not generator.is_done():
        generator.generate_next_token()
        out_tokens.append(generator.get_next_tokens()[0])
    elapsed = time.perf_counter() - t0

    raw = _tokenizer.decode(out_tokens).strip()
    for eos in PHI_EOS_TOKENS:
        while raw.endswith(eos):
            raw = raw[: -len(eos)].strip()

    return raw, len(out_tokens), elapsed


class ChatRequest(BaseModel):
    query: str
    system: Optional[str] = "You are a helpful AI assistant."
    max_tokens: Optional[int] = DEFAULT_MAX_TOKENS
    temperature: Optional[float] = DEFAULT_TEMPERATURE


class ChatResponse(BaseModel):
    response: str
    tokens_generated: int
    latency_ms: float
    tok_per_sec: float
    model: str = "phi-3.5-mini"


@app.get("/health")
def health():
    return {
        "status":      "ok" if _ready else ("error" if _load_error else "loading"),
        "ready":       _ready,
        "model":       "phi-3.5-mini-instruct-int4",
        "backend":     _backend or None,
        "load_time_s": _load_time_s,
        "error":       _load_error or None,
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    if not _ready:
        detail = f"Phi model not ready — {_load_error or 'still loading'}"
        raise HTTPException(503, detail)
    if not req.query.strip():
        raise HTTPException(400, "query must not be empty")

    loop = asyncio.get_event_loop()
    async with _lock:
        response, n_tokens, elapsed = await loop.run_in_executor(
            None,
            _generate_sync,
            req.system or "",
            req.query,
            req.max_tokens or DEFAULT_MAX_TOKENS,
            req.temperature if req.temperature is not None else DEFAULT_TEMPERATURE,
        )

    tps = round(n_tokens / elapsed, 1) if elapsed > 0 else 0.0
    log.info("Phi: %d tokens in %.1fs (%.1f tok/s)", n_tokens, elapsed, tps)
    return ChatResponse(
        response=response,
        tokens_generated=n_tokens,
        latency_ms=round(elapsed * 1000, 1),
        tok_per_sec=tps,
    )


@app.on_event("startup")
async def on_startup():
    global _lock
    _lock = asyncio.Lock()
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _load_model)


if __name__ == "__main__":
    uvicorn.run("phi_service:app", host="127.0.0.1", port=8112, log_level="info")
