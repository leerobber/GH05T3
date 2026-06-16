"""SAGE → SFT/DPO training data exporter.

Reads kairos_log.jsonl and converts elite proposals into training pairs
for train_local.py (SFT) or DPO fine-tuning.

Usage:
    python -m evolution.sft_export                     # SFT + DPO, default paths
    python -m evolution.sft_export --min-score 0.85    # lower threshold
    python -m evolution.sft_export --sft-only          # skip DPO pairs
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable

KAIROS_LOG = Path(__file__).parent / "kairos_log.jsonl"

_PROPOSER_INSTRUCTION = (
    "You are the GH05T3 SAGE Proposer. Propose ONE concrete, self-improvement "
    "change to GH05T3 that would measurably improve KAIROS, Memory Palace, "
    "Ghost Protocol, or a sub-agent. Technical, specific, shippable."
)
_PROPOSER_INPUT = "Propose one high-quality improvement to GH05T3."


def _read_kairos(log_path: Path) -> list[dict]:
    if not log_path.exists():
        return []
    records = []
    with open(log_path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return records


def export_sft(
    output_path: Path,
    log_path: Path = KAIROS_LOG,
    min_score: float = 0.90,
) -> int:
    """Export elite proposals as SFT training pairs (alpaca format).

    Returns number of pairs written.
    """
    records = _read_kairos(log_path)
    pairs = []
    seen = set()
    for r in records:
        score = r.get("score", 0.0)
        proposal = (r.get("proposal") or "").strip()
        verdict = (r.get("verdict") or "").upper()
        if score < min_score or not proposal or proposal in seen:
            continue
        if verdict not in {"PASS", "PARTIAL"}:
            continue
        seen.add(proposal)
        pairs.append({
            "instruction": _PROPOSER_INSTRUCTION,
            "input": _PROPOSER_INPUT,
            "output": proposal,
            "score": round(score, 4),
            "verdict": verdict,
            "agent_id": r.get("agent_id", "unknown"),
        })

    pairs.sort(key=lambda x: x["score"], reverse=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        for p in pairs:
            f.write(json.dumps(p) + "\n")
    return len(pairs)


def export_dpo(
    output_path: Path,
    log_path: Path = KAIROS_LOG,
    chosen_min: float = 0.90,
    rejected_max: float = 0.50,
) -> int:
    """Export DPO pairs: high-score (chosen) vs low-score (rejected) proposals.

    Format: {"prompt", "chosen", "rejected"}
    Returns number of pairs written.
    """
    records = _read_kairos(log_path)

    chosen = [
        r for r in records
        if r.get("score", 0) >= chosen_min
        and (r.get("verdict") or "").upper() in {"PASS", "PARTIAL"}
        and r.get("proposal", "").strip()
    ]
    rejected = [
        r for r in records
        if r.get("score", 0) <= rejected_max
        and (r.get("verdict") or "").upper() in {"FAIL", "PARTIAL"}
        and r.get("proposal", "").strip()
    ]

    if not chosen or not rejected:
        return 0

    pairs = []
    for i, c in enumerate(chosen):
        r = rejected[i % len(rejected)]
        pairs.append({
            "prompt": _PROPOSER_INPUT,
            "chosen": c["proposal"].strip(),
            "rejected": r["proposal"].strip(),
            "chosen_score": round(c.get("score", 0), 4),
            "rejected_score": round(r.get("score", 0), 4),
        })

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        for p in pairs:
            f.write(json.dumps(p) + "\n")
    return len(pairs)


def export_all(
    training_dir: Path | None = None,
    log_path: Path = KAIROS_LOG,
    min_score: float = 0.90,
    sft_only: bool = False,
) -> dict:
    """Export SFT and DPO data. Returns counts."""
    base = training_dir or Path(__file__).parents[1] / "training"
    sft_path = base / "sft_data_kairos.jsonl"
    dpo_path = base / "dpo_data_kairos.jsonl"

    n_sft = export_sft(sft_path, log_path=log_path, min_score=min_score)
    n_dpo = 0 if sft_only else export_dpo(dpo_path, log_path=log_path, chosen_min=min_score)

    return {
        "sft_pairs": n_sft,
        "dpo_pairs": n_dpo,
        "sft_path": str(sft_path),
        "dpo_path": str(dpo_path),
    }


# ── Sovereign model → training domain mapping ──────────────────────────────
AGENT_DOMAIN: dict[str, str] = {
    "gh05t3-sovereign":  "default",
    "avery-sovereign":   "default",
    "codex-sovereign":   "code",
    "oracle-sovereign":  "research",
    "nexus-sovereign":   "ops",
    "forge-sovereign":   "code",
    "sentinel-sovereign":"security",
}


def _normalize_agent_id(agent_id: str) -> str:
    """'ollama:codex-sovereign:latest' → 'codex-sovereign'"""
    name = agent_id.split(":")[-2] if agent_id.count(":") >= 2 else agent_id
    return name.split("/")[-1]


def export_per_agent(
    training_dir: Path | None = None,
    log_path: Path = KAIROS_LOG,
    min_score: float = 0.90,
) -> dict[str, int]:
    """Split KAIROS log by proposing agent and write one SFT file per domain.

    Returns {agent_name: n_pairs} for each agent that had qualifying proposals.
    Agents that map to the same domain are merged (codex + forge → code).
    """
    base = training_dir or Path(__file__).parents[1] / "training"
    records = _read_kairos(log_path)

    domain_records: dict[str, list[dict]] = {}
    for r in records:
        score    = r.get("score", 0.0)
        proposal = (r.get("proposal") or "").strip()
        verdict  = (r.get("verdict") or "").upper()
        if score < min_score or not proposal or verdict not in {"PASS", "PARTIAL"}:
            continue
        raw_agent = r.get("agent_id", "unknown")
        agent     = _normalize_agent_id(raw_agent)
        domain    = AGENT_DOMAIN.get(agent, "default")
        domain_records.setdefault(domain, []).append(r)

    counts: dict[str, int] = {}
    for domain, recs in domain_records.items():
        path = base / f"sft_data_{domain}.jsonl"
        seen = set()
        pairs = []
        for r in sorted(recs, key=lambda x: x.get("score", 0), reverse=True):
            proposal = (r.get("proposal") or "").strip()
            if proposal in seen:
                continue
            seen.add(proposal)
            pairs.append({
                "instruction": _PROPOSER_INSTRUCTION,
                "input":       _PROPOSER_INPUT,
                "output":      proposal,
                "score":       round(r.get("score", 0), 4),
                "verdict":     (r.get("verdict") or "").upper(),
                "agent_id":    r.get("agent_id", "unknown"),
            })
        base.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            for p in pairs:
                f.write(json.dumps(p) + "\n")
        counts[domain] = len(pairs)

    return counts


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export KAIROS log to SFT/DPO training data")
    parser.add_argument("--min-score", type=float, default=0.90)
    parser.add_argument("--sft-only", action="store_true")
    parser.add_argument("--log", type=Path, default=KAIROS_LOG)
    args = parser.parse_args()

    result = export_all(log_path=args.log, min_score=args.min_score, sft_only=args.sft_only)
    print(f"SFT pairs: {result['sft_pairs']}  →  {result['sft_path']}")
    if not args.sft_only:
        print(f"DPO pairs: {result['dpo_pairs']}  →  {result['dpo_path']}")
    if result["sft_pairs"] == 0:
        print("(no qualifying records yet — run more SAGE cycles to build archive)")
        sys.exit(0)
