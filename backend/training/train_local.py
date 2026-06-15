#!/usr/bin/env python3
"""
GH05T3 Local Training — Qwen2.5-7B-Instruct + QLoRA (4-bit) + Unsloth 2-3×
Runs on RTX 5050 (Blackwell sm_120, 8 GB VRAM).  No cloud needed.

One-time setup from repo root (run train.bat — it does this automatically):
    pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
    pip install unsloth                                              # 2-3x speedup
    pip install transformers>=4.40.2 peft>=0.10.0 trl>=0.8.6 accelerate>=0.29.3 \
                datasets>=2.19.0 "huggingface_hub>=0.22.0" "bitsandbytes>=0.44.0" kaggle

Then:
    python backend/training/train_local.py
    # OR on Windows:
    native\\windows\\train.bat

Speed path:
    Unsloth installed  → FastLanguageModel path:  ~30-45 min / 500 steps (2-3x faster)
    Unsloth missing    → Standard HF path:         ~60-90 min / 500 steps (baseline)
    Unsloth detects Blackwell sm_120 automatically — no extra config needed.
"""

import json
import logging
import os
import random
import sys
import warnings
from pathlib import Path

# ── Unsloth fast path — 2-3× speedup on Blackwell sm_120, zero config needed ──
try:
    from unsloth import FastLanguageModel as _UnslothModel
    _HAS_UNSLOTH = True
except ImportError:
    _UnslothModel = None
    _HAS_UNSLOTH = False

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
MAX_SEQ_LEN = 1024  # doubled: fills longer security-analysis examples; packing keeps VRAM flat
BATCH       = 2    # reduce to 1 if OOM
GRAD_ACCUM  = 4    # effective batch = 8

KAGGLE_DATASET = "tatortot/gh05t3-datasets"
KAGGLE_TOKEN   = os.environ.get("KAGGLE_API_TOKEN", "KGAT_929e7ea3c862ca57f07ee6ec736adc0d")

SYSTEM = (
    "You are GH05T3, an autonomous security and reasoning agent. "
    "You think carefully, reason step-by-step, and always prioritize "
    "detection and defense over exploitation."
)

# ── domain-specific system prompts ────────────────────────────────────────────
DOMAIN_SYSTEMS = {
    "default":  SYSTEM,
    "security": (
        "You are SENTINEL, GH05T3's Chief Security Officer. "
        "You specialize in threat analysis, CVE research, vulnerability assessment, "
        "and defensive security architecture. You think in attack trees and always "
        "reason from attacker perspective to build stronger defenses."
    ),
    "code": (
        "You are FORGE, GH05T3's CTO. You write clean, efficient, well-reasoned code. "
        "You perform deep code reviews, architectural analysis, refactoring, and "
        "debugging. You explain your reasoning step-by-step before writing code."
    ),
    "research": (
        "You are ORACLE, GH05T3's Chief Research Officer. "
        "You synthesize complex information, compare methodologies, survey literature, "
        "and produce comprehensive, well-structured research summaries. "
        "You cite sources, note uncertainty, and distinguish fact from inference."
    ),
    "ops": (
        "You are NEXUS, GH05T3's COO. You manage infrastructure, deployments, "
        "incident response, capacity planning, and operational excellence. "
        "You think in systems, anticipate failure modes, and create runbooks."
    ),
}

# ── domain → output directory ─────────────────────────────────────────────────
DOMAIN_OUT_DIRS = {
    "default":  REPO / "backend" / "models" / "gh05t3_lora_adapter",
    "security": REPO / "backend" / "models" / "security_adapter",
    "code":     REPO / "backend" / "models" / "code_adapter",
    "research": REPO / "backend" / "models" / "research_adapter",
    "ops":      REPO / "backend" / "models" / "ops_adapter",
}

# ── sovereign model → domain mapping ─────────────────────────────────────────
AGENT_DOMAIN = {
    "gh05t3-sovereign":   "default",
    "avery-sovereign":    "default",
    "codex-sovereign":    "code",
    "oracle-sovereign":   "research",
    "nexus-sovereign":    "ops",
    "forge-sovereign":    "code",
    "sentinel-sovereign": "security",
}


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

    # ── Sovereign Recall — highest quality source (pre-formatted ChatML) ──────
    recall_file = REPO / "backend" / "data" / "training" / "sovereign_recall.jsonl"
    recall_count = 0
    for rec in read_jsonl(recall_file):
        text = rec.get("text", "")
        quality = rec.get("quality", 0)
        if not text or quality < 4:          # only high-quality recall examples
            continue
        if "<|im_start|>user" not in text:   # must have at least one turn
            continue
        texts.append(text)
        recall_count += 1
    if recall_count:
        log.info("Sovereign Recall: +%d examples (quality≥4) from %s", recall_count, recall_file)

    if not texts:
        log.error("No training examples found in %s", data_dir)
        sys.exit(1)

    random.seed(42)
    random.shuffle(texts)
    log.info("Dataset: %d examples (%d from Sovereign Recall)", len(texts), recall_count)
    return Dataset.from_dict({"text": texts})


def build_domain_dataset(domain: str, data_dir: Path):
    """Build a domain-specific training dataset.

    security → CVE/threat/bug-bounty data (all security JSONL files)
    code     → reasoning chains + synthetic code review examples
    research → sovereign_recall (quality>=3) + research synthesis templates
    ops      → operational templates (generated inline, no external file needed)
    default  → falls through to build_dataset()
    """
    from datasets import Dataset

    if domain == "default":
        return build_dataset(data_dir)

    system = DOMAIN_SYSTEMS[domain]
    texts  = []

    if domain == "security":
        for rec in read_jsonl(data_dir / "adversarial_defense.jsonl"):
            t = rec.get("threat_vector", "")
            if not t:
                continue
            texts.append(chatml([
                {"role": "system",    "content": system},
                {"role": "user",      "content": f"Analyze this threat vector:\n\n{t}"},
                {"role": "assistant", "content":
                    f"**Exploitation Method:** {rec.get('exploitation_method','N/A')}\n\n"
                    f"**Detection Pattern:** {rec.get('detection_pattern','N/A')}\n\n"
                    f"**Mitigation Strategy:** {rec.get('mitigation_strategy','N/A')}"},
            ]))
        for rec in read_jsonl(data_dir / "cve_patterns.jsonl"):
            p = rec.get("vulnerability_pattern", "")
            if not p:
                continue
            ind = rec.get("discovery_indicators", [])
            texts.append(chatml([
                {"role": "system",    "content": system},
                {"role": "user",      "content": f"Assess {rec.get('source_cve','CVE-UNKNOWN')}."},
                {"role": "assistant", "content":
                    f"**Pattern:** {p}\n\n**Indicators:**\n" +
                    ("\n".join(f"• {x}" for x in ind) if isinstance(ind, list) else str(ind)) +
                    f"\n\n**Defensive Lessons:** {rec.get('defensive_lessons','N/A')}"},
            ]))
        for rec in read_jsonl(data_dir / "bug_bounty.jsonl"):
            tgt  = rec.get("target_system", "")
            vuln = rec.get("vulnerability_found", "")
            if not tgt or not vuln:
                continue
            texts.append(chatml([
                {"role": "system",    "content": system},
                {"role": "user",      "content": f"Bug bounty report: {tgt} — {vuln}"},
                {"role": "assistant", "content":
                    f"**Recon Method:** {rec.get('recon_method','N/A')}\n\n"
                    f"**Non-weaponized PoC:** {rec.get('non_weaponized_poc','N/A')}\n\n"
                    f"**Remediation:** {rec.get('remediation','N/A')}"},
            ]))

    elif domain == "code":
        for rec in read_jsonl(data_dir / "reasoning_chains.jsonl"):
            q = rec.get("question", "")
            s = rec.get("reasoning_steps", [])
            if not q or not isinstance(s, list):
                continue
            texts.append(chatml([
                {"role": "system",    "content": system},
                {"role": "user",      "content": q},
                {"role": "assistant", "content":
                    "**Analysis:**\n" + "\n".join(f"{i+1}. {x}" for i, x in enumerate(s)) +
                    f"\n\n**Implementation:** {rec.get('final_answer','N/A')}"},
            ]))
        # Synthetic code-review templates
        _CODE_TEMPLATES = [
            ("Review this Python function for correctness, edge cases, and style:\n\n```python\n{snippet}\n```",
             "**Issues found:**\n1. No input validation\n2. Missing error handling\n\n**Improved version:**\n```python\n# validated, edge-cases handled\n{snippet}\n```\n\n**Style:** follows PEP 8. Add docstring explaining params and return value."),
            ("Explain the time and space complexity of this algorithm:\n\n{snippet}",
             "**Time complexity:** O(n log n) — sorting dominates\n**Space complexity:** O(n) — output list\n\n**Reasoning:** The outer loop runs n times. Inner binary search is O(log n). Combined: O(n log n)."),
            ("What design pattern applies here and how would you refactor?\n\n{snippet}",
             "**Pattern:** Strategy pattern — behaviour varies by type\n**Refactored:** Extract an interface, inject the concrete strategy\n\n**Before:** tight coupling via if/elif\n**After:** `handler = STRATEGY_MAP[type]; result = handler.execute(data)`"),
        ]
        snippets = ["def f(x): return x*2", "for i in range(n): arr.sort()", "if t=='a': doA()\nelif t=='b': doB()"]
        for i, (q_tmpl, a_tmpl) in enumerate(_CODE_TEMPLATES * 30):
            snippet = snippets[i % len(snippets)]
            texts.append(chatml([
                {"role": "system",    "content": system},
                {"role": "user",      "content": q_tmpl.format(snippet=snippet)},
                {"role": "assistant", "content": a_tmpl.format(snippet=snippet)},
            ]))

    elif domain == "research":
        recall_file = REPO / "backend" / "data" / "training" / "sovereign_recall.jsonl"
        for rec in read_jsonl(recall_file):
            text    = rec.get("text", "")
            quality = rec.get("quality", 0)
            if not text or quality < 3:
                continue
            if "<|im_start|>user" not in text:
                continue
            texts.append(text)
        # Research synthesis templates
        _RESEARCH_Q = [
            "Provide a comprehensive survey of transformer architecture improvements since 2020.",
            "Compare BM25 vs dense retrieval for production RAG systems.",
            "What are the state-of-the-art techniques for reducing LLM hallucinations?",
            "Analyze the trade-offs between LoRA rank and adapter quality.",
            "Summarize the literature on mixture-of-experts scaling laws.",
        ]
        _RESEARCH_A = [
            "**Overview:** Transformer research has focused on efficiency, length extension, and reasoning.\n\n**Key advances:**\n1. Flash Attention (Dao et al., 2022) — IO-aware attention, 2-4× speedup\n2. RoPE positional encoding — length generalization\n3. Grouped-query attention — KV cache reduction\n\n**Current frontier:** sparse attention, state-space models (Mamba), hybrid architectures.",
            "**BM25 strengths:** exact keyword match, no GPU needed, interpretable, fast\n**Dense retrieval strengths:** semantic similarity, handles paraphrase, recall on rare queries\n\n**Production recommendation:** hybrid (RRF fusion of BM25 + dense) consistently outperforms either alone. Use BM25 as initial filter, dense re-ranker on top-k.",
            "**Techniques:**\n1. RAG — ground responses in retrieved evidence\n2. Constitutional AI — self-critique and revision\n3. Chain-of-thought prompting — forces reasoning before answer\n4. Calibration via RLHF — penalize confident wrong answers\n\n**Best practice:** combine RAG + CoT + refusal for unsupported claims.",
            "**Higher rank:** more parameters, better expressiveness, slower training, more storage\n**Lower rank (r=4–8):** faster, smaller, often sufficient for narrow domains\n\n**Empirical finding:** r=16, alpha=32 is a reliable starting point. Diminishing returns above r=64 for most tasks.",
            "**Key papers:** GShard (2021), Switch Transformer (2022), Mixtral (2024)\n\n**Scaling laws:** MoE models achieve same loss as dense models with ~3-4× fewer FLOPs per token. Routing collapse is the main failure mode. Load balancing loss is critical.",
        ]
        for q, a in zip(_RESEARCH_Q * 20, _RESEARCH_A * 20):
            texts.append(chatml([
                {"role": "system",    "content": system},
                {"role": "user",      "content": q},
                {"role": "assistant", "content": a},
            ]))

    elif domain == "ops":
        _OPS = [
            ("A service is returning 503 errors. Walk me through the incident response process.",
             "**Triage (0–5 min):**\n1. Check dashboards — CPU, memory, error rate, latency\n2. Identify affected endpoints and % of traffic impacted\n3. Check recent deploys (last 30 min)\n\n**Containment:**\n4. If recent deploy → rollback immediately\n5. If traffic spike → check rate limits, enable circuit breaker\n\n**Root cause:**\n6. Pull logs: `kubectl logs -l app=svc --since=30m`\n7. Correlate with dependency health checks\n\n**Resolution:**\n8. Apply fix, canary deploy, watch error rate return to baseline\n9. Write postmortem within 24h"),
            ("Design a deployment pipeline for a Python FastAPI service.",
             "**Stages:**\n1. **CI** — lint (ruff), type-check (mypy), unit tests, security scan (bandit)\n2. **Build** — Docker multi-stage build, minimal image\n3. **Staging** — deploy to staging, run integration + smoke tests\n4. **Canary** — 5% traffic for 30 min, watch error rate + p99 latency\n5. **Production** — full rollout, auto-rollback on error rate > 1%\n\n**Key practices:** immutable tags, health check endpoint, graceful shutdown (SIGTERM handler), rolling update strategy"),
            ("How do you capacity plan for 10× traffic growth?",
             "**Step 1 — Baseline:** measure current p50/p95/p99 latency, CPU %, memory % at current load\n**Step 2 — Bottleneck analysis:** identify the first constraint (usually DB, then app tier)\n**Step 3 — Load test:** use locust to simulate 2×, 5×, 10× load. Find where error rate increases.\n**Step 4 — Horizontal scaling:** stateless app tier → add replicas behind LB\n**Step 5 — DB scaling:** read replicas for read-heavy, sharding or Postgres connection pooling\n**Step 6 — Caching:** Redis in front of expensive queries (cache hit rate target: 80%+)\n**Headroom rule:** provision for 3× peak, alert at 60% utilization"),
            ("Write a runbook for rotating API keys in production.",
             "**Runbook: API Key Rotation**\n\n**Pre-checks:**\n- [ ] Identify all services using the key\n- [ ] Ensure new key is generated and tested in staging\n\n**Steps:**\n1. Generate new key in provider console\n2. Add new key to secrets manager alongside old key\n3. Deploy services with dual-key support (accept both during transition)\n4. Update all consumers to use new key (gradual, verify each)\n5. Verify new key traffic in logs\n6. Revoke old key\n7. Remove old key from secrets manager\n\n**Rollback:** Re-enable old key (keep 24h after rotation before deletion)"),
            ("Explain blue-green vs canary deployments and when to use each.",
             "**Blue-Green:**\n- Two identical environments, switch DNS/LB instantly\n- Zero downtime, instant rollback by switching back\n- Cost: 2× infrastructure during transition\n- Best for: major releases, DB migrations where you need clean cutover\n\n**Canary:**\n- Gradual traffic shift (1% → 10% → 50% → 100%)\n- Real user traffic validates before full rollout\n- Detects issues at small scale before blast radius grows\n- Best for: high-traffic services, A/B testing, risky changes\n\n**Rule of thumb:** use canary by default; blue-green when you need instant rollback or schema changes"),
        ]
        for q, a in _OPS * 30:
            texts.append(chatml([
                {"role": "system",    "content": system},
                {"role": "user",      "content": q},
                {"role": "assistant", "content": a},
            ]))

    if not texts:
        log.error("No training examples for domain=%s in %s", domain, data_dir)
        sys.exit(1)

    random.seed(42)
    random.shuffle(texts)
    log.info("Domain '%s' dataset: %d examples", domain, len(texts))
    return Dataset.from_dict({"text": texts})


def load_sage_sft(domain: str) -> list[str]:
    """Load KAIROS-exported SFT pairs for this domain and convert to ChatML.

    Reads backend/training/sft_data_{domain}.jsonl (written by sft_export.py).
    Returns [] gracefully if the file doesn't exist yet.
    """
    sft_path = REPO / "backend" / "training" / f"sft_data_{domain}.jsonl"
    if not sft_path.exists():
        return []

    system = DOMAIN_SYSTEMS.get(domain, SYSTEM)
    texts = []
    seen = set()
    with open(sft_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            proposal = (rec.get("output") or rec.get("completion") or "").strip()
            if not proposal or proposal in seen:
                continue
            seen.add(proposal)
            texts.append(chatml([
                {"role": "system",    "content": system},
                {"role": "user",      "content": rec.get("input", "Propose a GH05T3 improvement.")},
                {"role": "assistant", "content": proposal},
            ]))

    log.info("SAGE SFT augmentation: +%d examples from %s", len(texts), sft_path.name)
    return texts


# ── main ───────────────────────────────────────────────────────────────────────
def main():
    import argparse
    import torch

    parser = argparse.ArgumentParser(description="GH05T3 LoRA trainer — default or domain-specific")
    parser.add_argument("--domain", default=None,
                        choices=["default", "security", "code", "research", "ops"],
                        help="Domain adapter to train (default trains the base GH05T3 adapter)")
    parser.add_argument("--agent", default=None,
                        help="Sovereign agent name (e.g. codex-sovereign) — auto-selects domain")
    parser.add_argument("--output", default=None,
                        help="Override output directory (default: backend/models/<domain>_adapter)")
    parser.add_argument("--steps", type=int, default=MAX_STEPS,
                        help=f"Training steps (default: {MAX_STEPS})")
    cli = parser.parse_args()

    # --agent maps to domain; --domain takes precedence if both given
    if cli.agent and not cli.domain:
        agent_key = cli.agent.replace("ollama:", "").split(":")[0]
        domain = AGENT_DOMAIN.get(agent_key, "default")
        log.info("Agent %s → domain '%s'", cli.agent, domain)
    else:
        domain = cli.domain or "default"

    out_dir = Path(cli.output) if cli.output else DOMAIN_OUT_DIRS.get(domain, OUT_DIR)
    steps   = cli.steps

    if not torch.cuda.is_available():
        log.error("No CUDA GPU. Install: pip install torch --index-url https://download.pytorch.org/whl/cu128")
        sys.exit(1)

    gpu  = torch.cuda.get_device_properties(0)
    vram = gpu.total_memory / 1e9
    log.info("GPU: %s | %.1f GB | sm_%d%d | PyTorch %s",
             gpu.name, vram, gpu.major, gpu.minor, torch.__version__)

    # TF32 — Blackwell/Ampere tensor cores run matmul in TF32 at ~10× FP32 throughput.
    # Default is enabled on sm_80+ but explicit set prevents accidental torch.set_float32_matmul_precision override.
    if gpu.major >= 8:
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.allow_tf32 = True
        log.info("TF32 matmul: enabled (sm_%d%d)", gpu.major, gpu.minor)

    if vram < 6:
        log.error("Need >= 6 GB VRAM, found %.1f GB", vram)
        sys.exit(1)

    if gpu.major >= 12 and tuple(int(x) for x in torch.__version__.split(".")[:2]) < (2, 6):
        log.error("RTX 50-series (Blackwell) needs PyTorch >= 2.6. Got %s", torch.__version__)
        log.error("Fix: pip install torch --index-url https://download.pytorch.org/whl/cu128")
        sys.exit(1)

    from transformers import TrainingArguments
    from trl import SFTTrainer

    # Use bf16 on Ampere+ (sm_80+) and Blackwell — more numerically stable than fp16
    use_bf16 = gpu.major >= 8
    compute_dtype = torch.bfloat16 if use_bf16 else torch.float16
    log.info("Precision: %s", "bf16" if use_bf16 else "fp16")

    # Adjust batch for tight VRAM
    batch = BATCH if vram >= 8 else 1

    log.info("Domain: %s → %s", domain, out_dir)

    # ── data ──
    data_dir = ensure_data()
    dataset  = build_domain_dataset(domain, data_dir)

    # ── SAGE SFT augmentation — inject elite proposals from KAIROS archive ─────
    sage_texts = load_sage_sft(domain)
    if sage_texts:
        from datasets import concatenate_datasets, Dataset as HFDataset
        sage_ds = HFDataset.from_dict({"text": sage_texts})
        dataset  = concatenate_datasets([dataset, sage_ds])
        random.shuffle(dataset["text"])  # type: ignore[index]
        log.info("Dataset after SAGE augmentation: %d examples", len(dataset))

    # =========================================================================
    # Model + LoRA loading — two paths:
    #   A) Unsloth FastLanguageModel (installed) → 2-3× faster on Blackwell
    #   B) Standard HuggingFace QLoRA            → baseline fallback
    # =========================================================================
    if _HAS_UNSLOTH:
        log.info("Unsloth fast path — 2-3× speedup via fused Blackwell kernels")
        model, tokenizer = _UnslothModel.from_pretrained(
            model_name=MODEL_ID,
            max_seq_length=MAX_SEQ_LEN,
            dtype=compute_dtype,
            load_in_4bit=True,
        )
        # RSLoRA (Rank-Stabilized LoRA) — better gradient scaling at rank 16
        # use_gradient_checkpointing=True handled internally by Unsloth (reentrant=False safe)
        model = _UnslothModel.get_peft_model(
            model,
            r=LORA_RANK,
            lora_alpha=32,
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                            "gate_proj", "up_proj", "down_proj"],
            lora_dropout=0.05,
            bias="none",
            use_gradient_checkpointing=True,
            use_rslora=True,
        )
        tokenizer = tokenizer  # already loaded
    else:
        log.info("Unsloth not installed — standard HF path (install: pip install unsloth)")
        from transformers import (AutoModelForCausalLM, AutoTokenizer,
                                   BitsAndBytesConfig)
        from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training

        tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        # 7B fp16 = 14 GB → 4-bit NF4 = ~3.5 GB → fits in 8 GB
        bnb_cfg = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=compute_dtype,
            bnb_4bit_use_double_quant=True,
        )
        model = AutoModelForCausalLM.from_pretrained(
            MODEL_ID,
            quantization_config=bnb_cfg,
            device_map="cuda",
            trust_remote_code=True,
        )
        model.config.use_cache = False
        # prepare_model_for_kbit_training with use_gradient_checkpointing=False
        # so TrainingArguments owns checkpointing (RULE 2: use_reentrant=False)
        model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=False)

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

    log.info("Model loaded — %.1f/%.1f GB VRAM", torch.cuda.memory_allocated(0)/1e9, vram)
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total     = sum(p.numel() for p in model.parameters())
    log.info("LoRA: %s trainable / %s total (%.2f%%)",
             f"{trainable:,}", f"{total:,}", 100 * trainable / total)

    # ── training ──────────────────────────────────────────────────────────────
    ckpt_dir = CKPT_DIR / domain
    ckpt_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    grad_accum = GRAD_ACCUM if batch == BATCH else GRAD_ACCUM * 2

    # Gradient checkpointing: Unsloth owns it via get_peft_model(use_gradient_checkpointing=True)
    # Standard HF path: TrainingArguments must own it with use_reentrant=False (RULE 2)
    gc_kwargs = {} if _HAS_UNSLOTH else {
        "gradient_checkpointing": True,
        # CRITICAL (RULE 2): use_reentrant=True (default) reruns forward during backward.
        # With fp16/bf16 + PEFT hooks this produces NaN gradients → loss collapses.
        "gradient_checkpointing_kwargs": {"use_reentrant": False},
    }

    args = TrainingArguments(
        output_dir=str(ckpt_dir),
        max_steps=steps,
        per_device_train_batch_size=batch,
        gradient_accumulation_steps=grad_accum,
        **gc_kwargs,
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
        # Async data streaming — pre-tokenized tensors DMA into GPU while backward runs
        dataloader_pin_memory=True,
        dataloader_num_workers=2,   # 2 CPU workers saturate the DataLoader without OOM
    )

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        dataset_text_field="text",
        max_seq_length=MAX_SEQ_LEN,
        packing=True,   # concat examples to fill windows — ~2x training efficiency
        args=args,
    )

    log.info("Training — domain=%s steps=%d lr=%s batch=%d×%d=%d eff optim=paged_adamw_8bit",
             domain, steps, LR, batch, grad_accum, batch * grad_accum)

    stats = trainer.train()
    loss  = stats.training_loss
    log.info("Done — loss: %.4f | steps: %d", loss, stats.global_step)

    # RULE 3 — Collapse detection. Loss outside 0.3–10 means the adapter is useless.
    # 0.0 = gradient collapse (NaN killed updates), >10 = diverged, never converged.
    if not (0.3 < loss < 10):
        log.error("Training failed (loss=%.4f). Expected 0.3 < loss < 10.", loss)
        log.error("loss=0.0 → gradient collapse: check bitsandbytes>=0.44, use_reentrant=False")
        log.error("loss>10  → diverged: lower lr, check dataset quality")
        sys.exit(1)

    # ── save ──────────────────────────────────────────────────────────────────
    model.save_pretrained(str(out_dir))
    tokenizer.save_pretrained(str(out_dir))
    with open(out_dir / "training_config.json", "w") as f:
        json.dump({
            "model":         MODEL_ID,
            "domain":        domain,
            "lora_rank":     LORA_RANK,
            "steps":         stats.global_step,
            "final_loss":    loss,
            "dataset_size":  len(dataset),
            "max_seq_len":   MAX_SEQ_LEN,
            "gpu":           gpu.name,
            "sm":            f"{gpu.major}{gpu.minor}",
            "pytorch":       torch.__version__,
            "quantized":     True,    # inference server reads this → loads 4-bit
            "compute_dtype": "bf16" if use_bf16 else "fp16",
        }, f, indent=2)

    log.info("Adapter saved → %s", out_dir)
    if domain == "default":
        log.info("Set LLM_PROVIDER=gh05t3 in backend/.env then run run.bat")
    else:
        log.info("Domain adapter ready — LoRAFarm will auto-load for '%s' tasks", domain)

    # ── optional AWQ export (Blackwell sm_120 + vLLM NVFP4 fast path) ─────────
    if gpu.major >= 12:
        _try_awq_export(out_dir, tokenizer)


def _try_awq_export(adapter_dir: Path, tokenizer) -> None:
    """Merge LoRA adapter into base model, then AWQ-quantize for vLLM NVFP4.

    Requires: pip install autoawq
    Creates:  backend/models/gh05t3_lora_adapter-awq/
    Then set: GH05T3_BASE_MODEL=<awq_dir>  GH05T3_ADAPTER_PATH=""
    """
    try:
        from awq import AutoAWQForCausalLM  # type: ignore
        from peft import PeftModel
        from transformers import AutoModelForCausalLM
    except ImportError:
        log.info("autoawq not installed — skipping AWQ export "
                 "(pip install autoawq to enable NVFP4-ready merged model)")
        return

    import gc
    import shutil

    merged_dir = adapter_dir.parent / (adapter_dir.name + "-merged")
    awq_dir    = adapter_dir.parent / (adapter_dir.name + "-awq")
    try:
        # Step 1: load base model on CPU, merge adapter, save merged model
        log.info("AWQ export: loading %s on CPU to merge adapter...", MODEL_ID)
        base_model = AutoModelForCausalLM.from_pretrained(
            MODEL_ID, torch_dtype=torch.float16,
            device_map="cpu", low_cpu_mem_usage=True,
        )
        peft_model   = PeftModel.from_pretrained(base_model, str(adapter_dir))
        merged_model = peft_model.merge_and_unload()
        merged_dir.mkdir(parents=True, exist_ok=True)
        merged_model.save_pretrained(str(merged_dir))
        tokenizer.save_pretrained(str(merged_dir))

        # Free memory before quantization
        del base_model, peft_model, merged_model
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        # Step 2: AWQ quantize merged model; tokenizer required for calibration
        log.info("AWQ export: quantizing merged model → %s", awq_dir)
        awq_dir.mkdir(parents=True, exist_ok=True)
        awq_model = AutoAWQForCausalLM.from_pretrained(str(merged_dir))
        awq_model.quantize(
            tokenizer,
            quant_config={"w_bit": 4, "q_group_size": 128,
                          "zero_point": True, "version": "GEMM"},
        )
        awq_model.save_quantized(str(awq_dir))
        tokenizer.save_pretrained(str(awq_dir))
        log.info("AWQ export complete → %s", awq_dir)
        log.info("For max speed: GH05T3_BASE_MODEL=%s GH05T3_ADAPTER_PATH=", awq_dir)
    except Exception as exc:
        log.warning("AWQ export failed (non-fatal): %s", exc)
    finally:
        if merged_dir.exists():
            shutil.rmtree(merged_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
