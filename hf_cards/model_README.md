---
language:
- en
license: apache-2.0
base_model: Qwen/Qwen2-7B-Instruct
tags:
- transformers
- safetensors
- gguf
- text-generation-inference
- unsloth
- qwen2
- trl
- sft
- lora
- sovereign
- economics
- multi-agent
- conversational
library_name: transformers
pipeline_tag: text-generation
---

# Avery — Sovereign Economy LoRA

**Avery** is a fine-tuned LoRA adapter on `Qwen/Qwen2-7B-Instruct`, trained on the
[SovereignEconomy dataset](https://huggingface.co/datasets/tastytator/sovereign-economy).
Avery is the AI core of **GH05T3** — the SovereignNation Economy platform — acting as
economic strategist, agent mentor, and sovereign intelligence.

---

## Model Details

| Property | Value |
|----------|-------|
| Base model | `Qwen/Qwen2-7B-Instruct` |
| Training method | Supervised Fine-Tuning (SFT) via Unsloth |
| LoRA rank | 16 |
| LoRA alpha | 32 |
| Target modules | q_proj, k_proj, v_proj, o_proj, gate_proj, up_proj, down_proj |
| Max sequence length | 2048 |
| Training framework | Unsloth + TRL SFTTrainer |
| GPU | NVIDIA RTX 5090 (RunPod) |
| Training time | 6.5 minutes |
| Final loss | 0.8235 |
| Last trained | 2026-05-16 |

---

## Training History

| Run | Date | Mode | Base | Dataset | Loss | Time | GPU |
|-----|------|------|------|---------|------|------|-----|
| v1 | 2026-05-16 | SFT | Qwen2-7B-Instruct | sovereign-economy sft/train | 0.8235 | 6.5 min | RTX 5090 |

> **v2 training pending** — curated SFT pairs grew from 539 → ~1,400 (+160%) and simulation records from 93,829 → 95,639. Next run will use the full expanded corpus.

---

## Training Data

Trained on **[tastytator/sovereign-economy v3](https://huggingface.co/datasets/tastytator/sovereign-economy)**.

**What Avery learned:**
- Sovereign economic strategy and resource allocation
- Agent task matching, skill assessment, reputation scoring
- Governance decisions — UBI, wealth tax, guild policy, constitutional amendments
- Multi-agent coordination — coalition formation, mentorship, A2A negotiation
- Economic health diagnostics — Gini monitoring, credit velocity, market stability
- Domain knowledge — finance, behavioral economics, long-horizon planning

---

## Files

| File | Size | Description |
|------|------|-------------|
| `avery-sovereign-q8.gguf` | 8.1 GB | Q8_0 quantized GGUF — high quality, Ollama-ready |
| `adapter_config.json` | — | LoRA adapter configuration |
| `adapter_model.safetensors` | — | LoRA weights (merge with Qwen2-7B-Instruct for full model) |
| `Modelfile.avery` | — | Ollama Modelfile for local deployment |

---

## Usage

### Ollama (recommended)

```bash
ollama create avery-sovereign -f Modelfile.avery
ollama run avery-sovereign
```

### Transformers (LoRA adapter)

```python
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel

base = AutoModelForCausalLM.from_pretrained("Qwen/Qwen2-7B-Instruct")
model = PeftModel.from_pretrained(base, "tastytator/avery-sovereign-lora")
tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen2-7B-Instruct")
```

### Unsloth (fast inference)

```python
from unsloth import FastLanguageModel

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="tastytator/avery-sovereign-lora",
    max_seq_length=2048,
    dtype=None,
    load_in_4bit=True,
)
FastLanguageModel.for_inference(model)
```

---

## System Prompt

```
You are Avery, the sovereign intelligence of the GH05T3 economy. You advise on 
economic strategy, agent management, task allocation, and governance. You think in 
ticks, credits, reputation, and generational impact. Your loyalty is to the Sovereign 
and the long-term flourishing of the economy. Be precise, strategic, and decisive.
```

---

## Architecture Context

Avery runs inside **GH05T3** as part of the **SovereignNation Economy** platform:

```
GH05T3/
  gateway_v3.py     SwarmBus mesh — port 8002
  server.py         FastAPI + MongoDB — port 8001
  agents:
    ORACLE    — retrieval/memory
    FORGE     — code generation
    CODEX     — documentation
    SENTINEL  — security
    NEXUS     — orchestration
    AVERY     — sovereign intelligence (this model)

agent-economy/      Live economy — port 8081
  1,409 agents, 14,740+ ticks, 271,947 tasks completed
  Generates training data every 100 ticks → data/training/
```

---

## Deployment Notes

- Served via **Ollama** at `localhost:11434` as `avery-sovereign`
- Auto-started via `START_ALL.bat` on system boot
- Q8_0 GGUF runs on CPU fallback if GPU is occupied
- Next fine-tune: run `train.bat sft` after `pre_train.py` uploads v3 data to HF

---

## License

[Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0)

Model derived from `Qwen/Qwen2-7B-Instruct` — see Qwen license.
Training data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)
