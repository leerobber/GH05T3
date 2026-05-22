# SovereignNation Training — Quick Start

## Prerequisites

```bash
# Python 3.10+, pip, git
python3 --version   # ≥ 3.10
nvidia-smi          # confirm GPU is visible

# Install core deps (training deps auto-install at runtime)
pip install datasets huggingface_hub httpx anthropic
```

## Option A — Local GPU (RTX 5050 / 8GB VRAM)

```bash
# Generate all 95 DPO pairs (no GPU needed, ~30 seconds)
python sovereign_trainer_v5.py --generate-only --domain all

# Full training run — expect 2–4 hours on 8GB VRAM
HF_TOKEN=hf_... python sovereign_trainer_v5.py \
  --domain all \
  --mode orpo \
  --epochs 3 \
  --push
```

**VRAM guide:**
| GPU | VRAM | Expected speed |
|-----|------|----------------|
| RTX 5050 | 8GB | ~90 min / epoch |
| RTX 4070 | 12GB | ~50 min / epoch |
| RTX 4090 | 24GB | ~25 min / epoch |

## Option B — RunPod GPU Pod (Cloud)

```bash
# Launch an A40 / RTX 4090 pod on RunPod (~$0.69–1.50/hr)
# Template: RunPod PyTorch 2.1 (CUDA 12.1)

# SSH into pod, clone repo
git clone https://github.com/leerobber/GH05T3.git && cd GH05T3
git checkout claude/gh05t3-summary-pwjyi

# Run training
HF_TOKEN=hf_... python sovereign_trainer_v5.py \
  --domain all \
  --mode orpo \
  --epochs 3 \
  --push
```

Estimated cost: $2–5 for a full training run.

## Option C — Kaggle (Free T4 GPU)

```python
# In a Kaggle notebook cell:
!git clone https://github.com/leerobber/GH05T3.git
%cd GH05T3
!git checkout claude/gh05t3-summary-pwjyi
!HF_TOKEN="hf_..." python sovereign_trainer_v5.py \
    --domain engineering \
    --mode sft \
    --epochs 1 \
    --push
```

Note: Kaggle T4 = 16GB VRAM, 9 hours/session limit. Run one domain at a time.

---

## Training Modes

| Mode | Description | Best for |
|------|-------------|----------|
| `orpo` | Odds-Ratio Preference Optimization | Best quality, no reference model needed |
| `dpo` | Direct Preference Optimization | Standard preference learning |
| `sft` | Supervised Fine-Tuning on chosen only | Fastest, fallback if trl version mismatch |

---

## Dataset Commands

```bash
# Build dataset only (no training), inspect output
python sovereign_trainer_v5.py --generate-only --domain engineering
cat training_data/sovereign_v5/sovereign_v5_pairs.jsonl | python3 -m json.tool | head -80

# Push dataset to HuggingFace (no training)
HF_TOKEN=hf_... python sovereign_trainer_v5.py --generate-only --domain all --push

# Push agent mentor training data
HF_TOKEN=hf_... python push_agents_to_hub.py

# Push all 4 main datasets (cve_patterns, reasoning_chains, adversarial_defense, bug_bounty)
HF_TOKEN=hf_... python push_to_hub.py
```

---

## Agent-Specific Fine-Tuning

```bash
# Fine-tune individual agents from tastytator/sovereign-economy
HF_TOKEN=hf_... python train_sovereign_sft.py --agent oracle  --mode orpo --epochs 3
HF_TOKEN=hf_... python train_sovereign_sft.py --agent forge   --mode orpo --epochs 3
HF_TOKEN=hf_... python train_sovereign_sft.py --agent codex   --mode orpo --epochs 3
HF_TOKEN=hf_... python train_sovereign_sft.py --agent sentinel --mode orpo --epochs 3
HF_TOKEN=hf_... python train_sovereign_sft.py --agent nexus   --mode orpo --epochs 3
HF_TOKEN=hf_... python train_sovereign_sft.py --agent all     --mode orpo --epochs 3
```

---

## Troubleshooting

### CUDA OOM on 8GB VRAM

```bash
# Reduce gradient accumulation or use SFT mode
python sovereign_trainer_v5.py --mode sft --domain engineering
```

Or edit `sovereign_trainer_v5.py` line with `gradient_accumulation_steps = 8` → `16`.

### torch version mismatch

```bash
pip install "torch>=2.1.0" --index-url https://download.pytorch.org/whl/cu121
```

### `trl` version conflicts

```bash
pip install "trl==0.12.2" "peft==0.14.0" "accelerate==1.2.1" --force-reinstall
```

### unsloth not found (CPU-only machine)

The trainer auto-falls back to `transformers` + `bitsandbytes`. Training will be slower but functional.

### HF push fails with 403

Your token needs `write` access to `tastytator/sovereign-economy`.
Generate a new token at huggingface.co/settings/tokens with **write** scope.

---

## Output Files

```
training_data/sovereign_v5/
  sovereign_v5_pairs.jsonl      95 DPO pairs (chosen + rejected + domain + task)
  checkpoints/                  Training checkpoints (auto-resume on restart)
  sovereign_v5_adapter/         Final LoRA adapter weights + tokenizer
```

---

## Verification

After training completes:

```bash
# Confirm adapter files exist
ls training_data/sovereign_v5/sovereign_v5_adapter/
# Expected: adapter_config.json, adapter_model.bin (or .safetensors), tokenizer files

# Quick inference test (if on GPU machine)
python3 - <<'EOF'
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

base = AutoModelForCausalLM.from_pretrained("unsloth/Qwen2.5-Coder-7B-Instruct",
                                             load_in_4bit=True, device_map="auto")
tokenizer = AutoTokenizer.from_pretrained("unsloth/Qwen2.5-Coder-7B-Instruct")
model = PeftModel.from_pretrained(base, "training_data/sovereign_v5/sovereign_v5_adapter")
model.eval()

prompt = "<|im_start|>user\nDesign a token-bucket rate limiter.<|im_end|>\n<|im_start|>assistant\n"
inputs = tokenizer(prompt, return_tensors="pt").to("cuda")
out = model.generate(**inputs, max_new_tokens=256, temperature=0.7)
print(tokenizer.decode(out[0], skip_special_tokens=True))
EOF
```

---

## HuggingFace Repos

| Repo | Contents |
|------|---------|
| `tastytator/sovereign-economy` | Main dataset hub (configs: sft, security, agents, sovereign_v5) |
| `tastytator/sovereign-university-lora` | sovereign_trainer_v5 output adapter |
| `tastytator/oracle-sovereign-lora` | ORACLE specialist LoRA |
| `tastytator/forge-sovereign-lora` | FORGE specialist LoRA |
| `tastytator/codex-sovereign-lora` | CODEX specialist LoRA |
| `tastytator/sentinel-sovereign-lora` | SENTINEL specialist LoRA |
| `tastytator/nexus-sovereign-lora` | NEXUS specialist LoRA |
