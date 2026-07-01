"""Windows-safe model + LoRA loader â€” no TRL, constitution enforced."""
from __future__ import annotations

import gc
import logging
import os
from pathlib import Path

from oss.train.constitution import audit_no_adapter_fp16_cast, checkpointing_kwargs
from oss.train.schemas import TrainConfig

LOG = logging.getLogger("oss.train.loader")

_REPO = Path(__file__).resolve().parents[2]
os.environ.setdefault("HF_DEACTIVATE_ASYNC_LOAD", "1")


def load_train_stack(config: TrainConfig):
    """Return (model, tokenizer, gpu_info)."""
    import torch
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    gpu = torch.cuda.get_device_properties(0)
    vram = gpu.total_memory / 1e9
    use_bf16 = gpu.major >= 8
    compute_dtype = torch.bfloat16 if use_bf16 else torch.float16

    LOG.info("Loading %s (4bit=%s, dtype=%s)", config.model_id, config.load_4bit, compute_dtype)

    tokenizer = AutoTokenizer.from_pretrained(
        config.model_id, trust_remote_code=True, local_files_only=True,
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    offload_dir = _REPO / "backend" / "models" / "_sovereign_train_offload"
    offload_dir.mkdir(parents=True, exist_ok=True)
    max_memory = {0: f"{int(vram * config.gpu_memory_frac)}GiB", "cpu": "2GiB"}

    load_kw: dict = {
        "trust_remote_code": True,
        "low_cpu_mem_usage": True,
        "torch_dtype": compute_dtype,
        "device_map": {"": 0},
        "max_memory": max_memory,
        "offload_folder": str(offload_dir),
        "local_files_only": True,
    }

    if config.load_4bit:
        load_kw["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=compute_dtype,
            bnb_4bit_use_double_quant=True,
        )

    model_id = config.model_id
    try:
        model = AutoModelForCausalLM.from_pretrained(model_id, **load_kw)
    except OSError as exc:
        if "1455" in str(exc) or "paging file" in str(exc).lower():
            fallback = "Qwen/Qwen2.5-1.5B-Instruct"
            LOG.warning("Paging-file OOM â€” falling back to %s", fallback)
            gc.collect()
            torch.cuda.empty_cache()
            model_id = fallback
            model = AutoModelForCausalLM.from_pretrained(fallback, **load_kw)
        else:
            load_kw["local_files_only"] = False
            model = AutoModelForCausalLM.from_pretrained(model_id, **load_kw)
    except Exception:
        load_kw["local_files_only"] = False
        model = AutoModelForCausalLM.from_pretrained(model_id, **load_kw)

    model.config.use_cache = False
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=False)
    try:
        model.gradient_checkpointing_enable(
            gradient_checkpointing_kwargs=checkpointing_kwargs(),
        )
    except TypeError:
        model.gradient_checkpointing_enable()

    lora_cfg = LoraConfig(
        r=config.lora_rank,
        lora_alpha=config.lora_alpha,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora_cfg)
    audit_no_adapter_fp16_cast(model)

    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    LOG.info(
        "LoRA attached â€” %s trainable / %s total (%.2f%%)",
        f"{trainable:,}", f"{total:,}", 100 * trainable / max(total, 1),
    )
    LOG.info("VRAM after load: %.1f GB", torch.cuda.memory_allocated(0) / 1e9)

    return model, tokenizer, {
        "name": gpu.name,
        "vram_gb": round(vram, 1),
        "sm": f"{gpu.major}{gpu.minor}",
        "model_id": model_id,
        "use_bf16": use_bf16,
    }
