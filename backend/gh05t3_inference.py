"""
GH05T3 Local Inference Server
==============================

Serves the fine-tuned GH05T3 LoRA adapter as an OpenAI-compatible
/v1/chat/completions endpoint at port 8010 (primary GPU slot).

Usage:
    python gh05t3_inference.py

Env vars:
    GH05T3_ADAPTER_PATH   path to the LoRA adapter directory
                          (default: models/gh05t3_lora_adapter/gh05t3_lora_adapter)
    GH05T3_BASE_MODEL     HuggingFace model ID for the base
                          (default: Qwen/Qwen2.5-Coder-3B-Instruct)
    GH05T3_PORT           port to listen on (default: 8010)
    GH05T3_DEVICE         cuda / cpu (default: cuda if available)

The server loads the base model, merges the LoRA adapter for fast
inference, then serves requests in ChatML format.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import AsyncGenerator

import torch
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from peft import PeftModel
from pydantic import BaseModel
from transformers import AutoModelForCausalLM, AutoTokenizer

load_dotenv(Path(__file__).parent / ".env")

log = logging.getLogger("gh05t3.inference")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────

_BASE_DIR    = Path(__file__).parent
ADAPTER_PATH = os.environ.get(
    "GH05T3_ADAPTER_PATH",
    str(_BASE_DIR / "models/gh05t3_lora_adapter/gh05t3_lora_adapter"),
)
BASE_MODEL   = os.environ.get("GH05T3_BASE_MODEL",  "Qwen/Qwen2.5-Coder-3B-Instruct")
PORT         = int(os.environ.get("GH05T3_PORT",    "8010"))
DEVICE       = os.environ.get("GH05T3_DEVICE",      "cuda" if torch.cuda.is_available() else "cpu")
MAX_NEW_TOKENS = int(os.environ.get("GH05T3_MAX_TOKENS", "1024"))

SYSTEM_PROMPT = (
    "You are GH05T3, an autonomous security and reasoning agent. "
    "You think carefully, reason step-by-step, and always prioritize "
    "detection and defense over exploitation."
)

# ─────────────────────────────────────────────
# MODEL STATE
# ─────────────────────────────────────────────

_model     = None
_tokenizer = None
_ready     = False


def load_model() -> None:
    global _model, _tokenizer, _ready

    log.info("Loading base model: %s", BASE_MODEL)
    _tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, trust_remote_code=True)
    if _tokenizer.pad_token is None:
        _tokenizer.pad_token = _tokenizer.eos_token

    dtype = torch.float16 if DEVICE == "cuda" else torch.float32
    base = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        torch_dtype=dtype,
        device_map=DEVICE,
        trust_remote_code=True,
    )

    adapter_dir = Path(ADAPTER_PATH)
    if adapter_dir.exists() and (adapter_dir / "adapter_config.json").exists():
        log.info("Merging LoRA adapter: %s", ADAPTER_PATH)
        peft_model = PeftModel.from_pretrained(base, str(adapter_dir))
        _model = peft_model.merge_and_unload()   # bake adapters in for fast inference
        log.info("LoRA adapter merged")
    else:
        log.warning("Adapter not found at %s — serving base model only", ADAPTER_PATH)
        _model = base

    _model.eval()
    _ready = True
    used  = torch.cuda.memory_allocated(0) / 1e9 if DEVICE == "cuda" else 0
    total = torch.cuda.get_device_properties(0).total_memory / 1e9 if DEVICE == "cuda" else 0
    log.info("Model ready on %s — %.1f/%.1f GB", DEVICE, used, total)


# ─────────────────────────────────────────────
# CHATML HELPERS
# ─────────────────────────────────────────────

def _build_chatml(messages: list[dict]) -> str:
    """Convert OpenAI message list to ChatML string."""
    parts = []
    for m in messages:
        role    = m.get("role", "user")
        content = m.get("content", "")
        parts.append(f"<|im_start|>{role}\n{content}<|im_end|>")
    parts.append("<|im_start|>assistant\n")
    return "\n".join(parts)


def _inject_system(messages: list[dict]) -> list[dict]:
    """Ensure the first message is a system prompt."""
    if messages and messages[0].get("role") == "system":
        return messages
    return [{"role": "system", "content": SYSTEM_PROMPT}] + messages


# ─────────────────────────────────────────────
# GENERATION
# ─────────────────────────────────────────────

def _generate(messages: list[dict], max_new_tokens: int, temperature: float) -> str:
    messages  = _inject_system(messages)
    prompt    = _build_chatml(messages)
    inputs    = _tokenizer(prompt, return_tensors="pt").to(DEVICE)
    input_len = inputs["input_ids"].shape[1]

    with torch.no_grad():
        if temperature > 0:
            out = _model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=True,
                temperature=temperature,
                top_p=0.9,
                repetition_penalty=1.1,
            )
        else:
            out = _model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=False,
                repetition_penalty=1.1,
            )

    new_tokens = out[0][input_len:]
    return _tokenizer.decode(new_tokens, skip_special_tokens=True).strip()


# ─────────────────────────────────────────────
# FASTAPI APP
# ─────────────────────────────────────────────

app = FastAPI(title="GH05T3 Inference", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


class ChatMessage(BaseModel):
    role:    str
    content: str


class ChatRequest(BaseModel):
    model:          str = "gh05t3"
    messages:       list[ChatMessage]
    temperature:    float = 0.7
    max_tokens:     int = MAX_NEW_TOKENS
    stream:         bool = False


@app.get("/health")
async def health():
    return {"status": "ready" if _ready else "loading", "model": BASE_MODEL, "adapter": ADAPTER_PATH}


@app.get("/v1/models")
async def list_models():
    return {
        "object": "list",
        "data": [{
            "id":      "gh05t3",
            "object":  "model",
            "created": int(time.time()),
            "owned_by": "avery",
        }]
    }


@app.post("/v1/chat/completions")
async def chat_completions(req: ChatRequest):
    if not _ready:
        raise HTTPException(status_code=503, detail="Model still loading")

    messages = [{"role": m.role, "content": m.content} for m in req.messages]

    try:
        loop = asyncio.get_event_loop()
        text = await loop.run_in_executor(
            None, _generate, messages, req.max_tokens, req.temperature
        )
    except Exception as e:
        log.error("Generation error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

    resp_id = f"chatcmpl-{int(time.time())}"
    return {
        "id":      resp_id,
        "object":  "chat.completion",
        "created": int(time.time()),
        "model":   "gh05t3",
        "choices": [{
            "index":         0,
            "message":       {"role": "assistant", "content": text},
            "finish_reason": "stop",
        }],
        "usage": {
            "prompt_tokens":     -1,
            "completion_tokens": -1,
            "total_tokens":      -1,
        },
    }


# ─────────────────────────────────────────────
# ENTRYPOINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    load_model()
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")
