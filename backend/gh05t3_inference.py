"""
GH05T3 Local Inference Server
==============================
OpenAI-compatible /v1/chat/completions at port 8010.

Supports both:
  - Quantized adapters (7B+ trained with QLoRA): loads 4-bit, no merge
  - Small adapters (<=3B trained fp16): loads fp16, merges for speed

Auto-detection via training_config.json in the adapter directory.

Env vars:
    GH05T3_ADAPTER_PATH   adapter directory
                          (default: models/gh05t3_lora_adapter)
    GH05T3_BASE_MODEL     override base model (default: from training_config.json)
    GH05T3_PORT           port (default: 8010)
    GH05T3_LOAD_4BIT      force 4-bit load: "1" / "0" / "auto" (default: auto)
    GH05T3_MAX_TOKENS     max new tokens per request (default: 1024)
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Optional

import torch
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from peft import PeftModel
from pydantic import BaseModel
from transformers import AutoModelForCausalLM, AutoTokenizer

load_dotenv(Path(__file__).parent / ".env")

log = logging.getLogger("gh05t3.inference")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# ── config ─────────────────────────────────────────────────────────────────────
_BASE_DIR    = Path(__file__).parent
ADAPTER_PATH = os.environ.get(
    "GH05T3_ADAPTER_PATH",
    str(_BASE_DIR / "models" / "gh05t3_lora_adapter"),
)
PORT           = int(os.environ.get("GH05T3_PORT",        "8010"))
DEVICE         = os.environ.get("GH05T3_DEVICE",           "cuda" if torch.cuda.is_available() else "cpu")
MAX_NEW_TOKENS = int(os.environ.get("GH05T3_MAX_TOKENS",  "1024"))
LOAD_4BIT_ENV  = os.environ.get("GH05T3_LOAD_4BIT",       "auto")   # "1" | "0" | "auto"

# BASE_MODEL env override — normally read from training_config.json
_BASE_MODEL_OVERRIDE = os.environ.get("GH05T3_BASE_MODEL", "")

DEFAULT_BASE_MODEL = "Qwen/Qwen2.5-7B-Instruct"

SYSTEM_PROMPT = (
    "You are GH05T3, an autonomous security and reasoning agent. "
    "You think carefully, reason step-by-step, and always prioritize "
    "detection and defense over exploitation."
)

# ── state ──────────────────────────────────────────────────────────────────────
_model     = None
_tokenizer = None
_ready     = False
_model_id  = DEFAULT_BASE_MODEL


def _should_load_4bit(training_cfg: dict) -> bool:
    """Decide whether to use 4-bit quantized loading."""
    if LOAD_4BIT_ENV == "1":
        return True
    if LOAD_4BIT_ENV == "0":
        return False
    # auto: trust the flag saved at training time
    if training_cfg.get("quantized"):
        return True
    # auto fallback: check VRAM vs model size heuristic
    if DEVICE == "cuda" and torch.cuda.is_available():
        vram_gb = torch.cuda.get_device_properties(0).total_memory / 1e9
        model_id = training_cfg.get("model", DEFAULT_BASE_MODEL).lower()
        # 7B fp16 = 14 GB; if VRAM < 12 GB and model is 7B+ → need 4-bit
        is_large = any(f"{n}b" in model_id for n in ["7", "8", "13", "14", "32", "70"])
        if is_large and vram_gb < 12:
            return True
    return False


def load_model() -> None:
    global _model, _tokenizer, _ready, _model_id

    adapter_dir = Path(ADAPTER_PATH)

    # Read training config written by train_local.py
    training_cfg: dict = {}
    cfg_path = adapter_dir / "training_config.json"
    if cfg_path.exists():
        with open(cfg_path) as f:
            training_cfg = json.load(f)
        log.info("Training config: model=%s loss=%.4f steps=%d quantized=%s",
                 training_cfg.get("model", "?"),
                 training_cfg.get("final_loss", 0),
                 training_cfg.get("steps", 0),
                 training_cfg.get("quantized", False))

    base_model = (_BASE_MODEL_OVERRIDE
                  or training_cfg.get("model")
                  or DEFAULT_BASE_MODEL)
    _model_id  = base_model
    use_4bit   = _should_load_4bit(training_cfg)

    log.info("Loading base model: %s (4-bit=%s)", base_model, use_4bit)

    _tokenizer = AutoTokenizer.from_pretrained(base_model, trust_remote_code=True)
    if _tokenizer.pad_token is None:
        _tokenizer.pad_token = _tokenizer.eos_token

    if use_4bit:
        from transformers import BitsAndBytesConfig
        compute_dtype = (torch.bfloat16
                         if training_cfg.get("compute_dtype") == "bf16"
                         else torch.float16)
        bnb_cfg = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=compute_dtype,
            bnb_4bit_use_double_quant=True,
        )
        base = AutoModelForCausalLM.from_pretrained(
            base_model,
            quantization_config=bnb_cfg,
            device_map=DEVICE,
            trust_remote_code=True,
        )
    else:
        dtype = torch.float16 if DEVICE == "cuda" else torch.float32
        base = AutoModelForCausalLM.from_pretrained(
            base_model,
            torch_dtype=dtype,
            device_map=DEVICE,
            trust_remote_code=True,
        )

    has_adapter = (adapter_dir.exists() and
                   (adapter_dir / "adapter_config.json").exists())

    if has_adapter:
        peft = PeftModel.from_pretrained(base, str(adapter_dir))
        if use_4bit:
            # Cannot merge_and_unload a quantized model without dequantizing first.
            # Keep as PeftModel — inference is only ~5% slower than merged.
            _model = peft
            log.info("Adapter loaded (quantized — no merge)")
        else:
            _model = peft.merge_and_unload()
            log.info("Adapter merged into fp16 base")
    else:
        log.warning("No adapter found at %s — serving base model only", ADAPTER_PATH)
        _model = base

    _model.eval()
    if DEVICE == "cuda":
        used  = torch.cuda.memory_allocated(0) / 1e9
        total = torch.cuda.get_device_properties(0).total_memory / 1e9
        log.info("Ready on %s — %.1f/%.1f GB VRAM", DEVICE, used, total)
    else:
        log.info("Ready on CPU")

    _ready = True


# ── inference ──────────────────────────────────────────────────────────────────
def _build_chatml(messages: list[dict]) -> str:
    parts = [f"<|im_start|>{m['role']}\n{m['content']}<|im_end|>" for m in messages]
    parts.append("<|im_start|>assistant\n")
    return "\n".join(parts)


def _inject_system(messages: list[dict]) -> list[dict]:
    if messages and messages[0].get("role") == "system":
        return messages
    return [{"role": "system", "content": SYSTEM_PROMPT}] + messages


def _generate(messages: list[dict], max_new_tokens: int, temperature: float) -> str:
    messages  = _inject_system(messages)
    prompt    = _build_chatml(messages)
    inputs    = _tokenizer(prompt, return_tensors="pt").to(DEVICE)
    input_len = inputs["input_ids"].shape[1]

    gen_kwargs = dict(
        **inputs,
        max_new_tokens=max_new_tokens,
        repetition_penalty=1.1,
        pad_token_id=_tokenizer.eos_token_id,
    )
    if temperature > 0:
        gen_kwargs.update(do_sample=True, temperature=temperature, top_p=0.9)
    else:
        gen_kwargs.update(do_sample=False)

    with torch.no_grad():
        out = _model.generate(**gen_kwargs)

    return _tokenizer.decode(out[0][input_len:], skip_special_tokens=True).strip()


# ── FastAPI ────────────────────────────────────────────────────────────────────
app = FastAPI(title="GH05T3 Inference", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


class ChatMessage(BaseModel):
    role:    str
    content: str


class ChatRequest(BaseModel):
    model:       str   = "gh05t3"
    messages:    list[ChatMessage]
    temperature: float = 0.7
    max_tokens:  int   = MAX_NEW_TOKENS
    stream:      bool  = False


@app.get("/health")
async def health():
    return {
        "status":  "ready" if _ready else "loading",
        "model":   _model_id,
        "adapter": ADAPTER_PATH,
    }


@app.get("/v1/models")
async def list_models():
    return {
        "object": "list",
        "data": [{
            "id":       "gh05t3",
            "object":   "model",
            "created":  int(time.time()),
            "owned_by": "avery",
        }],
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

    return {
        "id":      f"chatcmpl-{int(time.time())}",
        "object":  "chat.completion",
        "created": int(time.time()),
        "model":   "gh05t3",
        "choices": [{
            "index":         0,
            "message":       {"role": "assistant", "content": text},
            "finish_reason": "stop",
        }],
        "usage": {"prompt_tokens": -1, "completion_tokens": -1, "total_tokens": -1},
    }


if __name__ == "__main__":
    load_model()
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")
