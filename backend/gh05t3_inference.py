"""
GH05T3 Local Inference Server â€” v3
====================================
OpenAI-compatible /v1/chat/completions at port 8010.

Backend auto-selection (priority order):
  1. vLLM AsyncLLMEngine  â€” NVFP4 on Blackwell sm_120 (~8,000 tok/s)
                            FP8   on Hopper  sm_90  (~4,000 tok/s)
                            BF16  fallback          (~1,000 tok/s)
                            True SSE streaming Â· multi-LoRA hot-swap (up to 8)
  2. HuggingFace + PEFT   â€” NF4 BitsAndBytes fallback (~300 tok/s)
                            SSE streaming via TextIteratorStreamer

Env vars:
    GH05T3_ADAPTER_PATH  adapter dir   (default: models/gh05t3_lora_adapter)
    GH05T3_BASE_MODEL    base model override
    GH05T3_PORT          port          (default: 8010)
    GH05T3_LOAD_4BIT     HF 4-bit: "1"/"0"/"auto"  (default: auto)
    GH05T3_MAX_TOKENS    max new tokens (default: 1024)
    GH05T3_FORCE_HF      "1" = skip vLLM, use HF path (default: "0")
    GH05T3_GPU_MEMORY    vLLM GPU memory utilization 0-1 (default: 0.90)
"""
from __future__ import annotations

import os

# Windows: parallel safetensor materialization causes access violations (torch 2.11 + transformers)
os.environ.setdefault("HF_DEACTIVATE_ASYNC_LOAD", "1")

import asyncio
import json
import logging
import threading
import time
import uuid
from pathlib import Path

import torch
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

load_dotenv(Path(__file__).parent / ".env")

log = logging.getLogger("gh05t3.inference")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# â”€â”€ env config â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
_BASE_DIR      = Path(__file__).parent
ADAPTER_PATH   = os.environ.get("GH05T3_ADAPTER_PATH",
                                str(_BASE_DIR / "models" / "gh05t3_lora_adapter"))
PORT           = int(os.environ.get("GH05T3_PORT",       "8010"))
DEVICE         = os.environ.get("GH05T3_DEVICE",
                                "cuda" if torch.cuda.is_available() else "cpu")
MAX_NEW_TOKENS = int(os.environ.get("GH05T3_MAX_TOKENS",  "1024"))
LOAD_4BIT_ENV  = os.environ.get("GH05T3_LOAD_4BIT",       "auto")
FORCE_HF       = os.environ.get("GH05T3_FORCE_HF",        "0") == "1"
GPU_MEM_UTIL   = float(os.environ.get("GH05T3_GPU_MEMORY", "0.90"))
MAX_CTX_LEN    = int(os.environ.get("GH05T3_MAX_CTX",     "32768"))   # extended context window
MAX_SEQS       = int(os.environ.get("GH05T3_MAX_SEQS",    "16"))      # concurrent batch slots
_BASE_MODEL_OVERRIDE = os.environ.get("GH05T3_BASE_MODEL", "")
DEFAULT_BASE_MODEL   = "Qwen/Qwen2.5-7B-Instruct"

SYSTEM_PROMPT = (
    "You are GH05T3, an autonomous security and reasoning agent. "
    "You think carefully, reason step-by-step, and always prioritize "
    "detection and defense over exploitation."
)

# â”€â”€ vLLM availability probe â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
_VLLM = False
if not FORCE_HF:
    try:
        from vllm import AsyncLLMEngine, AsyncEngineArgs, SamplingParams  # type: ignore
        from vllm.lora.request import LoRARequest  # type: ignore
        _VLLM = True
        log.info("vLLM found â€” AsyncLLMEngine will be primary backend")
    except ImportError:
        log.info("vLLM not installed â€” using HuggingFace transformers path")

# â”€â”€ runtime state â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
_vllm_engine  = None   # AsyncLLMEngine  (vLLM path)
_hf_model     = None   # PeftModel / AutoModelForCausalLM  (HF path)
_tokenizer    = None   # always loaded â€” prompt building for both backends
_ready        = False
_model_id     = DEFAULT_BASE_MODEL
_backend      = "hf"   # "vllm" | "hf"
_quant_type   = "none" # "nvfp4" | "fp8" | "nf4" | "none"
_tok_s_ema    = 0.0    # exponential moving avg of tokens/sec
_has_adapter  = False
_hf_lock      = None   # asyncio.Lock â€” serialize HF generation to prevent CUDA OOM


def _update_tok_s(new_val: float) -> None:
    global _tok_s_ema
    _tok_s_ema = 0.3 * new_val + 0.7 * _tok_s_ema if _tok_s_ema else new_val


def _pick_vllm_quant() -> str | None:
    """Best weight quantization for the installed GPU."""
    if not torch.cuda.is_available():
        return None
    major = torch.cuda.get_device_properties(0).major
    if major >= 12:
        return "nvfp4"  # Blackwell sm_120 â€” ~8 000 tok/s native
    if major >= 9:
        return "fp8"    # Hopper  sm_90  â€” ~4 000 tok/s native
    return None         # Ampere and older â€” vLLM uses BF16


def _pick_kv_cache_dtype() -> str:
    """fp8 KV cache cuts memory ~2x vs fp16, enabling longer context on the same VRAM.

    vLLM only accepts 'auto' or 'fp8' â€” it selects the optimal fp8 sub-format
    (e5m2 vs e4m3) internally based on hardware capability.
    Hopper (sm_90+) and Blackwell (sm_120+) both support fp8 natively.
    """
    if not torch.cuda.is_available():
        return "auto"
    major = torch.cuda.get_device_properties(0).major
    if major >= 9:
        return "fp8"   # Hopper + Blackwell â€” vLLM picks e4m3/e5m2 internally
    return "auto"


# â”€â”€ LoRA Farm â€” domain-specific adapter hot-swap â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class LoRAFarm:
    """Route generation requests to domain-specific LoRA adapters.

    Each domain adapter is a separate fine-tune trained on domain-specific data:
        security  â†’ models/security_adapter     (CVE, exploit reasoning, OWASP)
        code      â†’ models/code_adapter         (code generation, refactoring)
        research  â†’ models/research_adapter     (knowledge synthesis, summarization)
        ops       â†’ models/ops_adapter          (workflow planning, orchestration)
        default   â†’ models/gh05t3_lora_adapter  (general-purpose fine-tune)

    Adapters are ~150MB each. vLLM holds up to max_loras=8 in VRAM simultaneously,
    swapping on LRU. Falls back gracefully to the default adapter when a domain
    adapter hasn't been trained yet.
    """

    _DOMAIN_DIRS: dict[str, str] = {
        "security": "security_adapter",
        "code":     "code_adapter",
        "research": "research_adapter",
        "ops":      "ops_adapter",
        "quick":    "gh05t3_lora_adapter",
        "default":  "gh05t3_lora_adapter",
    }
    _LORA_INT_IDS: dict[str, int] = {
        "security": 1, "code": 2, "research": 3,
        "ops": 4, "quick": 5, "default": 6,
    }

    def __init__(self, base_dir: Path | None = None):
        self._base = base_dir or (Path(__file__).parent / "models")

    def get_lora_request(self, task_domain: str) -> LoRARequest | None:
        if not _VLLM:
            return None
        # Omni MoE: scientific domain â†’ adapter path (20 disciplines)
        try:
            from oss.forge.domains import resolve_domain
            from oss.forge.moe_farm import resolve_adapter_path
            sci_domain = resolve_domain(task_domain)
            bucket, adapter_path = resolve_adapter_path(self._base, sci_domain)
            domain = bucket if bucket in self._LORA_INT_IDS else "default"
        except Exception:
            domain = task_domain if task_domain in self._DOMAIN_DIRS else "default"
            adapter_path = self._base / self._DOMAIN_DIRS[domain]
            if not (adapter_path / "adapter_config.json").exists():
                adapter_path = self._base / "gh05t3_lora_adapter"
        if not (adapter_path / "adapter_config.json").exists():
            adapter_path = self._base / "gh05t3_lora_adapter"
        if not (adapter_path / "adapter_config.json").exists():
            return None
        return LoRARequest(
            lora_name       = domain,
            lora_int_id     = self._LORA_INT_IDS.get(domain, 6),
            lora_local_path = str(adapter_path),
        )

    def available_domains(self) -> dict[str, bool]:
        try:
            from oss.forge.moe_farm import list_moe_status
            return {k: v["trained"] for k, v in list_moe_status(self._base).items()}
        except Exception:
            return {
                domain: (self._base / subdir / "adapter_config.json").exists()
                for domain, subdir in self._DOMAIN_DIRS.items()
            }


_lora_farm: LoRAFarm | None = None


def get_lora_farm() -> "LoRAFarm":
    global _lora_farm
    if _lora_farm is None:
        _lora_farm = LoRAFarm()
    return _lora_farm
# â”€â”€ model loading â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def _resolve_adapter_dir(base: Path | None = None) -> Path:
    """Find adapter_config.json â€” handles nested training output layouts."""
    root = base or Path(ADAPTER_PATH)
    if (root / "adapter_config.json").exists():
        return root
    nested = root / root.name
    if (nested / "adapter_config.json").exists():
        return nested
    outputs = root / "outputs"
    if outputs.is_dir():
        for ckpt in sorted(outputs.glob("checkpoint-*"), reverse=True):
            if (ckpt / "adapter_config.json").exists():
                return ckpt
    return root


def load_model() -> None:
    global _tokenizer, _ready, _model_id, _has_adapter

    adapter_dir  = _resolve_adapter_dir()
    _has_adapter = adapter_dir.exists() and (adapter_dir / "adapter_config.json").exists()
    if not _has_adapter:
        # weights at root, config nested â€” symlink-less copy path for PEFT
        root = Path(ADAPTER_PATH)
        nested = root / root.name
        if (root / "adapter_model.safetensors").exists() and (nested / "adapter_config.json").exists():
            import shutil
            for name in ("adapter_config.json", "training_config.json"):
                src = nested / name
                if src.exists() and not (root / name).exists():
                    shutil.copy2(src, root / name)
            _has_adapter = (root / "adapter_config.json").exists()
            if _has_adapter:
                adapter_dir = root
                log.info("Adapter layout fixed: copied config to %s", root)

    training_cfg: dict = {}
    cfg_path = adapter_dir / "training_config.json"
    if cfg_path.exists():
        with open(cfg_path) as f:
            training_cfg = json.load(f)
        log.info("Adapter: model=%s  loss=%.4f  steps=%d",
                 training_cfg.get("model", "?"),
                 training_cfg.get("final_loss", 0),
                 training_cfg.get("steps", 0))

    base_model = _BASE_MODEL_OVERRIDE or training_cfg.get("model") or DEFAULT_BASE_MODEL
    _model_id  = base_model

    # Tokenizer always loaded for prompt building and HF path
    from transformers import AutoTokenizer
    _tokenizer = AutoTokenizer.from_pretrained(base_model, trust_remote_code=True)
    if _tokenizer.pad_token is None:
        _tokenizer.pad_token = _tokenizer.eos_token

    adapter_arg = adapter_dir if _has_adapter else None
    if _VLLM:
        _load_vllm(base_model, adapter_arg, training_cfg)
    else:
        _load_hf(base_model, adapter_arg, training_cfg)

    _ready = True


def _load_vllm(base_model: str, adapter_dir, training_cfg: dict) -> None:
    global _vllm_engine, _backend, _quant_type

    preferred = _pick_vllm_quant()
    quant_cascade = [preferred, None] if preferred else [None]

    for quant in quant_cascade:
        try:
            log.info("vLLM init: model=%s  quant=%s  mem=%.0f%%",
                     base_model, quant or "bf16", GPU_MEM_UTIL * 100)
            engine_args = AsyncEngineArgs(
                model                  = base_model,
                quantization           = quant,
                dtype                  = "auto",
                gpu_memory_utilization = GPU_MEM_UTIL,
                enable_lora            = (adapter_dir is not None),
                max_loras              = 8,
                max_lora_rank          = 64,
                enforce_eager          = False,        # CUDA graph compilation
                trust_remote_code      = True,
                disable_log_requests   = True,
                # Extended context + memory efficiency
                max_model_len          = MAX_CTX_LEN,  # 32K context (fp8 KV makes this free)
                kv_cache_dtype         = _pick_kv_cache_dtype(),  # fp8 = ~2x KV memory reduction
                max_num_seqs           = MAX_SEQS,     # concurrent sequences for batching
                enable_chunked_prefill = True,         # efficient long-prompt processing
                enable_prefix_caching  = True,         # reuse KV cache for shared prefixes
            )
            _vllm_engine = AsyncLLMEngine.from_engine_args(engine_args)
            _quant_type  = quant or "none"
            _backend     = "vllm"
            log.info("vLLM ready: quant=%s  lora=%s", _quant_type, adapter_dir is not None)
            return
        except Exception as exc:
            if quant is not None:
                log.warning("vLLM quant=%s failed: %s â€” trying bf16", quant, exc)
            else:
                log.warning("vLLM bf16 init failed: %s â€” falling back to HF path", exc)
                _load_hf(base_model, adapter_dir, training_cfg)
                return


def _load_hf(base_model: str, adapter_dir, training_cfg: dict) -> None:
    global _hf_model, _backend, _quant_type
    from transformers import AutoModelForCausalLM

    use_4bit    = _should_load_4bit(training_cfg)
    _quant_type = "nf4" if use_4bit else "none"
    log.info("HF model: %s  4-bit=%s", base_model, use_4bit)

    # Stream weights to GPU â€” avoids Windows page-file exhaustion (os error 1455)
    import gc
    gc.collect()
    if DEVICE == "cuda" and torch.cuda.is_available():
        torch.cuda.empty_cache()
        vram = torch.cuda.get_device_properties(0).total_memory
        _dev_map = "auto"
        _max_mem = {0: f"{int(vram * 0.85 / (1024**3))}GiB", "cpu": "2GiB"}
    else:
        _dev_map = DEVICE
        _max_mem = None
    _offload = _BASE_DIR / "models" / "_offload"
    _offload.mkdir(parents=True, exist_ok=True)
    _load_kw: dict = {
        "trust_remote_code": True,
        "low_cpu_mem_usage": True,
        "local_files_only": True,
        # Let transformers lazy-load slices (lower peak RAM than disable_mmap full read)
        "offload_folder": str(_offload),
    }
    if _max_mem is not None:
        _load_kw["max_memory"] = _max_mem

    if use_4bit:
        from transformers import BitsAndBytesConfig
        c_dtype = (torch.bfloat16 if training_cfg.get("compute_dtype") == "bf16"
                   else torch.float16)
        base = AutoModelForCausalLM.from_pretrained(
            base_model,
            quantization_config=BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=c_dtype,
                bnb_4bit_use_double_quant=True,
            ),
            device_map=_dev_map,
            **_load_kw,
        )
    else:
        dtype = torch.float16 if DEVICE == "cuda" else torch.float32
        base  = AutoModelForCausalLM.from_pretrained(
            base_model, torch_dtype=dtype, device_map=_dev_map, **_load_kw,
        )

    if adapter_dir is not None:
        from peft import PeftModel
        peft      = PeftModel.from_pretrained(base, str(adapter_dir))
        _hf_model = peft if use_4bit else peft.merge_and_unload()
        log.info("Adapter %s", "loaded (4-bit, no merge)" if use_4bit else "merged into fp16")
    else:
        log.warning("No adapter at %s â€” serving base model only", ADAPTER_PATH)
        _hf_model = base

    _hf_model.eval()
    _backend = "hf"

    if DEVICE == "cuda":
        used  = torch.cuda.memory_allocated(0) / 1e9
        total = torch.cuda.get_device_properties(0).total_memory / 1e9
        log.info("HF ready on %s â€” %.1f/%.1f GB VRAM", DEVICE, used, total)


def _should_load_4bit(training_cfg: dict) -> bool:
    if LOAD_4BIT_ENV == "1": return True
    if LOAD_4BIT_ENV == "0": return False
    if training_cfg.get("quantized"): return True
    if DEVICE == "cuda" and torch.cuda.is_available():
        vram = torch.cuda.get_device_properties(0).total_memory / 1e9
        mid  = training_cfg.get("model", DEFAULT_BASE_MODEL).lower()
        if any(f"{n}b" in mid for n in ["7","8","13","14","32","70"]) and vram < 12:
            return True
    return False


# â”€â”€ prompt â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def _build_chatml(messages: list[dict]) -> str:
    parts = [f"<|im_start|>{m['role']}\n{m['content']}<|im_end|>" for m in messages]
    parts.append("<|im_start|>assistant\n")
    return "\n".join(parts)


def _inject_system(messages: list[dict]) -> list[dict]:
    if messages and messages[0].get("role") == "system":
        return messages
    return [{"role": "system", "content": SYSTEM_PROMPT}] + messages


# â”€â”€ vLLM generation â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
async def _vllm_stream_tokens(prompt: str, max_tokens: int, temperature: float,
                               req_id: str, task_domain: str = "default"):
    """Async-yield raw text tokens from vLLM. Aborts the request on cancellation."""
    lora = get_lora_farm().get_lora_request(task_domain)
    prev = ""
    try:
        async for out in _vllm_engine.generate(
            prompt,
            SamplingParams(
                temperature        = max(temperature, 0.0),
                top_p              = 0.9 if temperature > 0 else 1.0,
                max_tokens         = max_tokens,
                repetition_penalty = 1.1,
            ),
            req_id,
            lora_request=lora,
        ):
            if out.outputs:
                text  = out.outputs[0].text
                delta = text[len(prev):]
                prev  = text
                if delta:
                    yield delta
    finally:
        # Free GPU resources if the client disconnects mid-stream
        await _vllm_engine.abort(req_id)


async def _vllm_generate_full(prompt: str, max_tokens: int, temperature: float,
                               task_domain: str = "default") -> tuple[str, int, int]:
    req_id = str(uuid.uuid4())
    full_text = ""
    p_toks = c_toks = 0
    try:
        async for out in _vllm_engine.generate(
            prompt,
            SamplingParams(
                temperature        = max(temperature, 0.0),
                top_p              = 0.9 if temperature > 0 else 1.0,
                max_tokens         = max_tokens,
                repetition_penalty = 1.1,
            ),
            req_id,
            lora_request=get_lora_farm().get_lora_request(task_domain),
        ):
            if out.finished and out.outputs:
                full_text = out.outputs[0].text.strip()
                c_toks    = len(out.outputs[0].token_ids)
                p_toks    = len(out.prompt_token_ids) if out.prompt_token_ids else 0
    finally:
        await _vllm_engine.abort(req_id)
    return full_text, p_toks, c_toks


# â”€â”€ HF generation â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def _hf_generate_sync(messages: list[dict], max_tokens: int, temperature: float
                       ) -> tuple[str, int, int]:
    msgs = messages if (messages and messages[0].get("role") == "system") else _inject_system(messages)
    prompt = _build_chatml(msgs)
    inputs = _tokenizer(prompt, return_tensors="pt").to(DEVICE)
    p_len  = inputs["input_ids"].shape[1]
    gen_kw = dict(**inputs, max_new_tokens=max_tokens,
                  repetition_penalty=1.1, pad_token_id=_tokenizer.eos_token_id)
    if temperature > 0:
        gen_kw.update(do_sample=True, temperature=temperature, top_p=0.9)
    else:
        gen_kw.update(do_sample=False)
    with torch.no_grad():
        out = _hf_model.generate(**gen_kw)
    c_ids = out[0][p_len:]
    return _tokenizer.decode(c_ids, skip_special_tokens=True).strip(), p_len, len(c_ids)


async def _hf_stream_tokens(messages: list[dict], max_tokens: int, temperature: float):
    """Async-yield raw text tokens from HF via TextIteratorStreamer.

    Three robustness properties:
    - Unbounded queue: avoids QueueFull crash from call_soon_threadsafe
    - streamer.end() in finally: unblocks the reader thread even on OOM/exception
    - stop_event: signals the generation thread to exit early on client disconnect
    """
    from transformers import StoppingCriteria, TextIteratorStreamer

    class _StopOnEvent(StoppingCriteria):
        def __init__(self, event: threading.Event) -> None:
            self._event = event
        def __call__(self, input_ids, scores, **kwargs) -> bool:
            return self._event.is_set()

    prompt     = _build_chatml(_inject_system(messages))
    inputs     = _tokenizer(prompt, return_tensors="pt").to(DEVICE)
    stop_event = threading.Event()
    streamer   = TextIteratorStreamer(_tokenizer, skip_prompt=True, skip_special_tokens=True)
    gen_kw     = dict(**inputs, max_new_tokens=max_tokens,
                      repetition_penalty=1.1, pad_token_id=_tokenizer.eos_token_id,
                      streamer=streamer, stopping_criteria=[_StopOnEvent(stop_event)])
    if temperature > 0:
        gen_kw.update(do_sample=True, temperature=temperature, top_p=0.9)
    else:
        gen_kw.update(do_sample=False)

    loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
    q: asyncio.Queue[str | None]    = asyncio.Queue()  # unbounded â€” avoids QueueFull

    def _reader():
        for tok in streamer:
            loop.call_soon_threadsafe(q.put_nowait, tok)
        loop.call_soon_threadsafe(q.put_nowait, None)

    def _gen():
        try:
            with torch.no_grad():
                _hf_model.generate(**gen_kw)
        except Exception as exc:
            log.error("HF generation error: %s", exc)
        finally:
            streamer.end()  # unblocks _reader even if generate() raised

    gen_t  = threading.Thread(target=_gen,    daemon=True)
    read_t = threading.Thread(target=_reader, daemon=True)
    gen_t.start()
    read_t.start()

    try:
        while True:
            tok = await q.get()
            if tok is None:
                break
            if tok:
                yield tok
    finally:
        stop_event.set()  # signal generate() to exit early if client disconnected
        gen_t.join(timeout=5.0)


# â”€â”€ unified SSE response â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
async def _sse_stream(messages: list[dict], max_tokens: int, temperature: float,
                      task_domain: str = "default"):
    """Yield SSE data: lines for both vLLM and HF backends."""
    cid   = f"chatcmpl-{uuid.uuid4().hex[:8]}"
    ts    = int(time.time())
    start = time.monotonic()
    n_tok = 0

    base = {"id": cid, "object": "chat.completion.chunk", "created": ts, "model": "gh05t3"}

    if _backend == "vllm":
        prompt = _build_chatml(
            messages if (messages and messages[0].get("role") == "system") else _inject_system(messages)
        )
        source = _vllm_stream_tokens(prompt, max_tokens, temperature,
                                      str(uuid.uuid4()), task_domain)
    else:
        source = _hf_stream_tokens(
            messages if (messages and messages[0].get("role") == "system") else _inject_system(messages),
            max_tokens, temperature,
        )

    async for token in source:
        chunk = {**base, "choices": [{"index": 0, "delta": {"content": token},
                                       "finish_reason": None}]}
        yield f"data: {json.dumps(chunk)}\n\n"
        n_tok += 1

    elapsed = time.monotonic() - start
    if elapsed > 0.1 and n_tok > 0:
        _update_tok_s(n_tok / elapsed)

    yield f"data: {json.dumps({**base, 'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}]})}\n\n"
    yield "data: [DONE]\n\n"


# â”€â”€ FastAPI â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
app = FastAPI(title="GH05T3 Inference", version="3.0.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
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
    task_domain: str   = ""   # scientific or legacy domain slug â€” Omni MoE routes adapter
    session_id:  str   = ""   # epigenetic session affinity across turns


@app.get("/health")
async def health():
    omni_moe: dict = {}
    try:
        from oss.forge.inference_router import _load_elite_strands
        from oss.forge.moe_farm import list_moe_status
        strands = _load_elite_strands()
        omni_moe = {
            "paradigm": "omni_strand_moe",
            "elite_strands": len(strands),
            "scientific_domains": len(list_moe_status(Path(__file__).parent / "models")),
            "novel_methods": [
                "spectral_classify", "superposition_blend", "holographic_context",
                "epigenetic_session", "attractor_hysteresis", "methylation_temperature",
                "crispr_splice", "fractal_drill_down", "entropy_gated_exploration",
                "memetic_allele_vote", "topological_persistence", "causal_counterfactual_route",
                "neuro_symbolic_verify",
            ],
        }
    except Exception as exc:
        omni_moe = {"error": str(exc)}
    return {
        "status":        "ready" if _ready else "loading",
        "model":         _model_id,
        "adapter":       ADAPTER_PATH,
        "backend":       _backend,
        "quant":         _quant_type,
        "tok_s":         round(_tok_s_ema, 1),
        "lora_adapters": get_lora_farm().available_domains(),
        "omni_moe":      omni_moe,
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
            "metadata": {"backend": _backend, "quant": _quant_type},
        }],
    }


def _plan_route(req: ChatRequest) -> tuple[list[dict], str, float, dict]:
    """Omni MoE routing â€” spectral classify, holographic context, epigenetic bias."""
    messages = [{"role": m.role, "content": m.content} for m in req.messages]
    try:
        from oss.forge.inference_router import plan_inference_route
        route = plan_inference_route(
            messages,
            task_domain=req.task_domain,
            session_id=req.session_id,
            base_temperature=req.temperature,
        )
        return (
            route.augmented_messages,
            route.adapter_bucket,
            route.scaled_temperature,
            route.to_dict(),
        )
    except Exception as exc:
        log.warning("Omni MoE route fallback: %s", exc)
        domain = req.task_domain or "default"
        if not req.task_domain:
            try:
                from ghost_llm import _classify_task
                combined = " ".join(
                    m["content"] for m in messages if m["role"] in ("system", "user")
                )
                domain = _classify_task(combined)
            except Exception:
                pass
        return messages, domain, req.temperature, {"fallback": True, "adapter_bucket": domain}


@app.post("/v1/route/plan")
async def route_plan(req: ChatRequest):
    """Preview Omni MoE routing without generation."""
    _, bucket, temp, meta = _plan_route(req)
    return {"adapter_bucket": bucket, "scaled_temperature": temp, "route": meta}


@app.post("/v1/chat/completions")
async def chat_completions(req: ChatRequest):
    if not _ready:
        raise HTTPException(status_code=503, detail="Model still loading")

    messages, domain, temperature, route_meta = _plan_route(req)

    if req.stream:
        return StreamingResponse(
            _sse_stream(messages, req.max_tokens, temperature, domain),
            media_type="text/event-stream",
            headers={
                "X-Accel-Buffering": "no",
                "Cache-Control": "no-cache",
                "X-Omni-Domain": route_meta.get("domain", domain),
            },
        )

    start = time.monotonic()
    try:
        if _backend == "vllm":
            prompt = _build_chatml(messages)
            text, p_toks, c_toks = await _vllm_generate_full(
                prompt, req.max_tokens, temperature, domain
            )
        else:
            global _hf_lock
            if _hf_lock is None:
                _hf_lock = asyncio.Lock()
            async with _hf_lock:
                loop = asyncio.get_event_loop()
                text, p_toks, c_toks = await loop.run_in_executor(
                    None, _hf_generate_sync, messages, req.max_tokens, temperature,
                )
    except Exception as exc:
        log.error("Generation error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

    # Neuro-symbolic verifier (novel post-generation gate)
    verify: dict = {}
    try:
        from oss.forge.inference_router import neuro_symbolic_verify
        from oss.forge.domains import resolve_domain
        verify = neuro_symbolic_verify(text, resolve_domain(route_meta.get("domain", domain)))
    except Exception:
        pass

    elapsed = time.monotonic() - start
    if elapsed > 0 and c_toks > 0:
        _update_tok_s(c_toks / elapsed)

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
        "usage": {
            "prompt_tokens":     p_toks,
            "completion_tokens": c_toks,
            "total_tokens":      p_toks + c_toks,
        },
        "omni_moe": {**route_meta, "verifier": verify},
    }


if __name__ == "__main__":
    load_model()
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")
