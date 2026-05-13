#!/usr/bin/env python3
"""
GH05T3 Local Training
Qwen2.5-Coder-3B-Instruct + LoRA rank 16 → backend/models/gh05t3_lora_adapter/

One-time setup (run from repo root):
    pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
    pip install transformers==4.40.2 peft==0.10.0 trl==0.8.6 accelerate==0.29.3 datasets==2.19.0 "huggingface_hub>=0.22.0" kaggle

Then:
    python backend/training/train_local.py
    # or on Windows: native\\windows\\train.bat
"""

import os, sys, json, random, warnings, logging
from pathlib import Path

warnings.filterwarnings("ignore", category=FutureWarning, message=".*resume_download.*")
warnings.filterwarnings("ignore", category=UserWarning,   message=".*use_reentrant.*")
warnings.filterwarnings("ignore", category=FutureWarning, message=".*`tokenizers`.*")
os.environ["TOKENIZERS_PARALLELISM"] = "false"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("gh05t3")

# ── paths ──────────────────────────────────────────────────────────────────────
REPO     = Path(__file__).resolve().parent.parent.parent   # GH05T3/
DATA_DIR = REPO / "backend" / "data" / "training"
OUT_DIR  = REPO / "backend" / "models" / "gh05t3_lora_adapter"
CKPT_DIR = REPO / "backend" / "training" / "checkpoints"

# ── hyperparams ────────────────────────────────────────────────────────────────
MODEL_ID    = "Qwen/Qwen2.5-Coder-3B-Instruct"
LORA_RANK   = 16
MAX_STEPS   = 500
LR          = 2e-5
MAX_GRAD    = 0.3
WARMUP      = 50
MAX_SEQ_LEN = 512
BATCH       = 2    # reduce to 1 if OOM on <8 GB VRAM
GRAD_ACCUM  = 4    # effective batch = BATCH * GRAD_ACCUM = 8

SYSTEM = (
    "You are GH05T3, an autonomous security and reasoning agent. "
    "You think carefully, reason step-by-step, and always prioritize "
    "detection and defense over exploitation."
)

KAGGLE_DATASET  = "tatortot/gh05t3-datasets"
KAGGLE_TOKEN    = os.environ.get("KAGGLE_API_TOKEN", "KGAT_929e7ea3c862ca57f07ee6ec736adc0d")


# ── data ───────────────────────────────────────────────────────────────────────
def ensure_data() -> Path:
    required = ["adversarial_defense.jsonl", "reasoning_chains.jsonl",
                "cve_patterns.jsonl", "bug_bounty.jsonl"]
    if all((DATA_DIR / f).exists() for f in required):
        log.info(f"Data cache: {DATA_DIR}")
        return DATA_DIR

    log.info(f"Downloading {KAGGLE_DATASET} ...")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    import subprocess
    result = subprocess.run(
        ["kaggle", "datasets", "download", "-d", KAGGLE_DATASET,
         "--path", str(DATA_DIR), "--unzip"],
        capture_output=True, text=True,
        env={**os.environ, "KAGGLE_API_TOKEN": KAGGLE_TOKEN},
    )
    if result.returncode != 0:
        log.error(f"Kaggle download failed:\n{result.stderr}")
        log.error("Put the .jsonl files manually in: backend/data/training/")
        sys.exit(1)
    log.info("Download complete")
    return DATA_DIR


def read_jsonl(p: Path):
    if not p.exists():
        log.warning(f"Missing: {p.name}")
        return
    with open(p, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    yield json.loads(line)
                except Exception:
                    pass


def chatml(msgs):
    return "\n".join(f"<|im_start|>{m['role']}\n{m['content']}<|im_end|>" for m in msgs)


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
                f"\n\n**Answer:** {rec.get('final_answer','N/A')}"},
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
                f"\n\n**Lessons:** {rec.get('defensive_lessons','N/A')}"},
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
                f"**Recon:** {rec.get('recon_method','N/A')}\n\n"
                f"**PoC:** {rec.get('non_weaponized_poc','N/A')}\n\n"
                f"**Remediation:** {rec.get('remediation','N/A')}"},
        ]))

    if not texts:
        log.error(f"No training examples found in {data_dir}")
        sys.exit(1)

    random.seed(42)
    random.shuffle(texts)
    log.info(f"Dataset: {len(texts)} examples")
    return Dataset.from_dict({"text": texts})


# ── main ───────────────────────────────────────────────────────────────────────
def main():
    import torch

    if not torch.cuda.is_available():
        log.error("No CUDA GPU. Install: pip install torch --index-url https://download.pytorch.org/whl/cu128")
        sys.exit(1)

    gpu   = torch.cuda.get_device_properties(0)
    vram  = gpu.total_memory / 1e9
    sm    = f"sm_{gpu.major}{gpu.minor}"
    log.info(f"GPU: {gpu.name} | {vram:.1f} GB | {sm} | PyTorch {torch.__version__}")

    if vram < 6:
        log.error(f"Need >= 6 GB VRAM, found {vram:.1f} GB")
        sys.exit(1)

    # Blackwell (sm_120) needs PyTorch >= 2.6. Older builds produce gibberish.
    if gpu.major >= 12 and torch.__version__ < "2.6":
        log.error(f"RTX 50-series requires PyTorch 2.6+. Got {torch.__version__}")
        log.error("Fix: pip install torch --index-url https://download.pytorch.org/whl/cu128")
        sys.exit(1)

    batch      = BATCH if vram >= 8 else 1
    grad_accum = GRAD_ACCUM if batch == BATCH else GRAD_ACCUM * 2

    log.info(f"Config: steps={MAX_STEPS} lr={LR} batch={batch}×{grad_accum}={batch*grad_accum} eff")

    from transformers import AutoTokenizer, AutoModelForCausalLM, TrainingArguments
    from peft import LoraConfig, get_peft_model
    from trl import SFTTrainer

    # ── data ──
    data_dir = ensure_data()
    dataset  = build_dataset(data_dir)

    # ── model ──
    log.info(f"Loading {MODEL_ID} ...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        torch_dtype=torch.float16,
        device_map="cuda",
        trust_remote_code=True,
    )
    model.config.use_cache = False
    log.info(f"Model loaded — {torch.cuda.memory_allocated(0)/1e9:.1f}/{vram:.1f} GB used")

    # ── LoRA ──
    model.enable_input_require_grads()
    lora_cfg = LoraConfig(
        r=LORA_RANK,
        lora_alpha=32,
        target_modules=["q_proj","k_proj","v_proj","o_proj","gate_proj","up_proj","down_proj"],
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora_cfg)

    # CRITICAL: PEFT inits adapter weights fp32. Base model is fp16.
    # fp32 adapters + fp16 base + fp16=True training → GradScaler detects NaN at step 10,
    # permanently skips updates → loss stays 0.0 forever. Cast everything to fp16 here.
    for _, p in model.named_parameters():
        if p.requires_grad:
            p.data = p.data.to(torch.float16)

    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total     = sum(p.numel() for p in model.parameters())
    dtype     = next(p for p in model.parameters() if p.requires_grad).dtype
    log.info(f"LoRA: {trainable:,} trainable / {total:,} total ({100*trainable/total:.2f}%) dtype={dtype}")

    # ── training args ──
    CKPT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    args = TrainingArguments(
        output_dir=str(CKPT_DIR),
        max_steps=MAX_STEPS,
        per_device_train_batch_size=batch,
        gradient_accumulation_steps=grad_accum,
        gradient_checkpointing=True,
        # use_reentrant=True (default) reruns forward during backward; combined with
        # fp16 + enable_input_require_grads hook this produces NaN gradients.
        # use_reentrant=False avoids the recomputation issue.
        gradient_checkpointing_kwargs={"use_reentrant": False},
        warmup_steps=WARMUP,
        learning_rate=LR,
        fp16=True,
        bf16=False,
        max_grad_norm=MAX_GRAD,
        logging_steps=10,
        optim="adamw_torch",
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

    log.info("Training started ...")
    stats = trainer.train()
    loss  = stats.training_loss

    log.info(f"Done — loss: {loss:.4f} | steps: {stats.global_step}")

    if loss == 0.0 or loss > 100:
        log.error(f"Training failed (loss={loss}). Gradient collapse.")
        log.error("Verify: adapter dtype == fp16, use_reentrant=False, lr <= 2e-5")
        sys.exit(1)

    # ── save ──
    model.save_pretrained(str(OUT_DIR))
    tokenizer.save_pretrained(str(OUT_DIR))
    with open(OUT_DIR / "training_config.json", "w") as f:
        json.dump({
            "model": MODEL_ID,
            "lora_rank": LORA_RANK,
            "steps": stats.global_step,
            "final_loss": loss,
            "dataset_size": len(dataset),
            "gpu": gpu.name,
            "pytorch": torch.__version__,
        }, f, indent=2)

    log.info(f"Adapter → {OUT_DIR}")
    log.info("Add  LLM_PROVIDER=gh05t3  to backend/.env to activate.")


if __name__ == "__main__":
    main()
