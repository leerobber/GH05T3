#!/usr/bin/env python3
"""
GH05T3 Local Training — Qwen2.5-7B-Instruct + QLoRA (4-bit)
Runs on RTX 5050 (Blackwell, 8 GB VRAM).  No cloud needed.

One-time setup from repo root (run train.bat — it does this automatically):
    pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
    pip install transformers==4.40.2 peft==0.10.0 trl==0.8.6 accelerate==0.29.3 \
                datasets==2.19.0 "huggingface_hub>=0.22.0" "bitsandbytes>=0.44.0" kaggle

Then:
    python backend/training/train_local.py
    # OR on Windows:
    native\\windows\\train.bat
"""

import json
import logging
import os
import random
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore", category=FutureWarning, message=".*resume_download.*")
warnings.filterwarnings("ignore", category=UserWarning,   message=".*use_reentrant.*")
warnings.filterwarnings("ignore", category=FutureWarning, message=".*tokenizers.*")
os.environ["TOKENIZERS_PARALLELISM"] = "false"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("gh05t3-train")

# ── paths ──────────────────────────────────────────────────────────────────────
REPO     = Path(__file__).resolve().parent.parent.parent
DATA_DIR = REPO / "backend" / "data" / "training"
OUT_DIR  = REPO / "backend" / "models" / "gh05t3_lora_adapter"
CKPT_DIR = REPO / "backend" / "training" / "checkpoints"

# ── config ─────────────────────────────────────────────────────────────────────
MODEL_ID    = "Qwen/Qwen2.5-7B-Instruct"   # 7B beats 3B for reasoning; fits in 8 GB via 4-bit
LORA_RANK   = 16
MAX_STEPS   = 500
LR          = 2e-5
MAX_GRAD    = 0.3
WARMUP      = 50
MAX_SEQ_LEN = 512
BATCH       = 2    # reduce to 1 if OOM
GRAD_ACCUM  = 4    # effective batch = 8

KAGGLE_DATASET = "tatortot/gh05t3-datasets"
KAGGLE_TOKEN   = os.environ.get("KAGGLE_API_TOKEN", "KGAT_929e7ea3c862ca57f07ee6ec736adc0d")

SYSTEM = (
    "You are GH05T3, an autonomous security and reasoning agent. "
    "You think carefully, reason step-by-step, and always prioritize "
    "detection and defense over exploitation."
)


# ── data ───────────────────────────────────────────────────────────────────────
def ensure_data() -> Path:
    required = [
        "adversarial_defense.jsonl",
        "reasoning_chains.jsonl",
        "cve_patterns.jsonl",
        "bug_bounty.jsonl",
    ]
    if all((DATA_DIR / f).exists() for f in required):
        log.info("Data cache: %s", DATA_DIR)
        return DATA_DIR

    log.info("Downloading %s ...", KAGGLE_DATASET)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    import subprocess
    r = subprocess.run(
        ["kaggle", "datasets", "download", "-d", KAGGLE_DATASET,
         "--path", str(DATA_DIR), "--unzip"],
        capture_output=True, text=True,
        env={**os.environ, "KAGGLE_API_TOKEN": KAGGLE_TOKEN},
    )
    if r.returncode != 0:
        log.error("Kaggle download failed:\n%s", r.stderr)
        log.error("Copy .jsonl files manually to: %s", DATA_DIR)
        sys.exit(1)
    return DATA_DIR


def read_jsonl(p: Path):
    if not p.exists():
        log.warning("Missing: %s", p.name)
        return
    with open(p, encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if s:
                try:
                    yield json.loads(s)
                except Exception:
                    pass


def chatml(msgs):
    return "\n".join(
        f"<|im_start|>{m['role']}\n{m['content']}<|im_end|>" for m in msgs
    )


def build_dataset(data_dir: Path):
    from datasets import Dataset

    texts = []

    for rec in read_jsonl(data_dir / "adversarial_defense.jsonl"):
        t = rec.get("threat_vector", "")
        if not t:
            continue
        texts.append(chatml([
            {"role": "system",    "content": SYSTEM},
            {"role": "user",      "content": f"Analyze this threat:\n\n{t}"},
            {"role": "assistant", "content":
                f"**Exploitation:** {rec.get('exploitation_method','N/A')}\n\n"
                f"**Detection:** {rec.get('detection_pattern','N/A')}\n\n"
                f"**Mitigation:** {rec.get('mitigation_strategy','N/A')}"},
        ]))

    for rec in read_jsonl(data_dir / "reasoning_chains.jsonl"):
        q = rec.get("question", "")
        s = rec.get("reasoning_steps", [])
        if not q or not isinstance(s, list):
            continue
        texts.append(chatml([
            {"role": "system",    "content": SYSTEM},
            {"role": "user",      "content": q},
            {"role": "assistant", "content":
                "**Reasoning:**\n" + "\n".join(f"{i+1}. {x}" for i, x in enumerate(s)) +
                f"\n\n**Answer:** {rec.get('final_answer', 'N/A')}"},
        ]))

    for rec in read_jsonl(data_dir / "cve_patterns.jsonl"):
        p = rec.get("vulnerability_pattern", "")
        if not p:
            continue
        ind = rec.get("discovery_indicators", [])
        texts.append(chatml([
            {"role": "system",    "content": SYSTEM},
            {"role": "user",      "content": f"Analyze {rec.get('source_cve','CVE')} vulnerability."},
            {"role": "assistant", "content":
                f"**Pattern:** {p}\n\n**Indicators:**\n" +
                ("\n".join(f"• {x}" for x in ind) if isinstance(ind, list) else str(ind)) +
                f"\n\n**Lessons:** {rec.get('defensive_lessons', 'N/A')}"},
        ]))

    for rec in read_jsonl(data_dir / "bug_bounty.jsonl"):
        tgt  = rec.get("target_system", "")
        vuln = rec.get("vulnerability_found", "")
        if not tgt or not vuln:
            continue
        texts.append(chatml([
            {"role": "system",    "content": SYSTEM},
            {"role": "user",      "content": f"Security research on {tgt}: {vuln}"},
            {"role": "assistant", "content":
                f"**Recon:** {rec.get('recon_method', 'N/A')}\n\n"
                f"**PoC:** {rec.get('non_weaponized_poc', 'N/A')}\n\n"
                f"**Remediation:** {rec.get('remediation', 'N/A')}"},
        ]))

    if not texts:
        log.error("No training examples found in %s", data_dir)
        sys.exit(1)

    random.seed(42)
    random.shuffle(texts)
    log.info("Dataset: %d examples", len(texts))
    return Dataset.from_dict({"text": texts})


# ── main ───────────────────────────────────────────────────────────────────────
def main():
    import torch

    if not torch.cuda.is_available():
        log.error("No CUDA GPU. Install: pip install torch --index-url https://download.pytorch.org/whl/cu128")
        sys.exit(1)

    gpu  = torch.cuda.get_device_properties(0)
    vram = gpu.total_memory / 1e9
    log.info("GPU: %s | %.1f GB | sm_%d%d | PyTorch %s",
             gpu.name, vram, gpu.major, gpu.minor, torch.__version__)

    if vram < 6:
        log.error("Need >= 6 GB VRAM, found %.1f GB", vram)
        sys.exit(1)

    if gpu.major >= 12 and tuple(int(x) for x in torch.__version__.split(".")[:2]) < (2, 6):
        log.error("RTX 50-series (Blackwell) needs PyTorch >= 2.6. Got %s", torch.__version__)
        log.error("Fix: pip install torch --index-url https://download.pytorch.org/whl/cu128")
        sys.exit(1)

    from transformers import (AutoModelForCausalLM, AutoTokenizer,
                               BitsAndBytesConfig, TrainingArguments)
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from trl import SFTTrainer

    # Use bf16 on Ampere+ (sm_80+) and Blackwell — more numerically stable than fp16
    use_bf16 = gpu.major >= 8
    compute_dtype = torch.bfloat16 if use_bf16 else torch.float16
    log.info("Precision: %s", "bf16" if use_bf16 else "fp16")

    # Adjust batch for tight VRAM
    batch = BATCH if vram >= 8 else 1

    # ── data ──
    data_dir = ensure_data()
    dataset  = build_dataset(data_dir)

    # ── tokenizer ──
    log.info("Loading %s ...", MODEL_ID)
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # ── 4-bit quantized base model ─────────────────────────────────────────────
    # 7B fp16 = 14 GB → doesn't fit in 8 GB.  4-bit NF4 = ~3.5 GB → fits easily.
    bnb_cfg = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=compute_dtype,
        bnb_4bit_use_double_quant=True,   # nested quant saves ~0.4 GB extra
    )
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        quantization_config=bnb_cfg,
        device_map="cuda",
        trust_remote_code=True,
    )
    model.config.use_cache = False
    log.info("Model loaded — %.1f/%.1f GB VRAM", torch.cuda.memory_allocated(0)/1e9, vram)

    # ── prepare for k-bit training ─────────────────────────────────────────────
    # Handles enable_input_require_grads() and casts layer norms to fp32 for stability.
    # use_gradient_checkpointing=False here — let TrainingArguments own it so we can
    # pass gradient_checkpointing_kwargs={"use_reentrant": False} (see below).
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=False)

    # ── LoRA ──────────────────────────────────────────────────────────────────
    # No manual fp16 cast needed: bitsandbytes compute_dtype handles adapter precision.
    lora_cfg = LoraConfig(
        r=LORA_RANK,
        lora_alpha=32,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora_cfg)
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total     = sum(p.numel() for p in model.parameters())
    log.info("LoRA: %s trainable / %s total (%.2f%%)",
             f"{trainable:,}", f"{total:,}", 100 * trainable / total)

    # ── training ──────────────────────────────────────────────────────────────
    CKPT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    grad_accum = GRAD_ACCUM if batch == BATCH else GRAD_ACCUM * 2

    args = TrainingArguments(
        output_dir=str(CKPT_DIR),
        max_steps=MAX_STEPS,
        per_device_train_batch_size=batch,
        gradient_accumulation_steps=grad_accum,
        gradient_checkpointing=True,
        # CRITICAL: use_reentrant=True (default) reruns forward during backward.
        # With fp16/bf16 + PEFT hooks this produces NaN gradients → loss collapses.
        gradient_checkpointing_kwargs={"use_reentrant": False},
        warmup_steps=WARMUP,
        learning_rate=LR,
        fp16=not use_bf16,
        bf16=use_bf16,
        max_grad_norm=MAX_GRAD,
        logging_steps=10,
        # paged_adamw_8bit keeps optimizer state in CPU-paged memory → ~500 MB instead of ~2 GB
        optim="paged_adamw_8bit",
        lr_scheduler_type="cosine",
        seed=42,
        save_strategy="steps",
        save_steps=100,
        save_total_limit=3,
        report_to="none",
    )

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        dataset_text_field="text",
        max_seq_length=MAX_SEQ_LEN,
        packing=False,
        args=args,
    )

    log.info("Training — steps=%d lr=%s batch=%d×%d=%d eff optim=paged_adamw_8bit",
             MAX_STEPS, LR, batch, grad_accum, batch * grad_accum)

    stats = trainer.train()
    loss  = stats.training_loss
    log.info("Done — loss: %.4f | steps: %d", loss, stats.global_step)

    if loss == 0.0 or loss > 100:
        log.error("Training failed (loss=%.4f). Gradient collapse detected.", loss)
        log.error("Verify: bitsandbytes >= 0.44, use_reentrant=False, lr <= 2e-5")
        sys.exit(1)

    # ── save ──────────────────────────────────────────────────────────────────
    model.save_pretrained(str(OUT_DIR))
    tokenizer.save_pretrained(str(OUT_DIR))
    with open(OUT_DIR / "training_config.json", "w") as f:
        json.dump({
            "model":        MODEL_ID,
            "lora_rank":    LORA_RANK,
            "steps":        stats.global_step,
            "final_loss":   loss,
            "dataset_size": len(dataset),
            "gpu":          gpu.name,
            "pytorch":      torch.__version__,
            "quantized":    True,    # inference server reads this → loads 4-bit
            "compute_dtype": "bf16" if use_bf16 else "fp16",
        }, f, indent=2)

    log.info("Adapter saved → %s", OUT_DIR)
    log.info("Add  LLM_PROVIDER=gh05t3  to backend/.env then start run.bat")


if __name__ == "__main__":
    main()
