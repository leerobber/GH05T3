"""Sovereign Train engine — orchestrates dataset → loop → save."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from oss.train.agents import resolve_agent
from oss.train.constitution import (
    ConstitutionViolation,
    assert_final_loss,
    assert_gpu_allowed,
)
from oss.train.dataset import build_examples
from oss.train.loader import load_train_stack
from oss.train.loop import SovereignLoop
from oss.train.schemas import TrainJob, TrainResult, TrainSource
from oss.train.tokenize import build_tokenized_dataset

LOG = logging.getLogger("oss.train.engine")
_REPO = Path(__file__).resolve().parents[2]


def run_training(job: TrainJob) -> TrainResult:
    """Run a full sovereign training job for one agent."""
    profile = resolve_agent(job.agent_id)
    out_dir = job.output_dir or profile.output_path
    out_dir = Path(out_dir)
    cfg = job.config

    gpu_info = assert_gpu_allowed()
    examples, manifest = build_examples(
        profile.agent_id,
        cfg.sources or [TrainSource.FORGE, TrainSource.ELITE],
        seed=cfg.seed,
    )

    if job.dry_run:
        return TrainResult(
            agent_id=profile.agent_id,
            success=True,
            final_loss=0.0,
            steps=0,
            examples=len(examples),
            output_dir=str(out_dir),
            adapter_path=str(out_dir),
            gpu=gpu_info.get("gpu", ""),
            notes=f"dry_run manifest={manifest}",
        )

    model, tokenizer, load_info = load_train_stack(cfg)
    tokenized = build_tokenized_dataset(tokenizer, examples, max_seq_len=cfg.max_seq_len)

    loop = SovereignLoop(
        model,
        tokenizer,
        tokenized,
        max_steps=cfg.max_steps,
        learning_rate=cfg.learning_rate,
        max_grad_norm=cfg.max_grad_norm,
        batch_size=cfg.batch_size,
        grad_accum=cfg.grad_accum,
        warmup_steps=cfg.resolved_warmup(),
        use_bf16=load_info["use_bf16"],
        log_every=cfg.log_every,
        seed=cfg.seed,
    )

    try:
        stats = loop.run()
    except ConstitutionViolation:
        raise

    final_loss = float(stats["final_loss"])
    assert_final_loss(final_loss)

    out_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(out_dir))
    tokenizer.save_pretrained(str(out_dir))

    meta = {
        "paradigm": "sovereign_omni_strand",
        "agent_id": profile.agent_id,
        "model": load_info["model_id"],
        "lora_rank": cfg.lora_rank,
        "steps": stats["steps"],
        "final_loss": final_loss,
        "dataset_size": len(examples),
        "manifest": manifest,
        "gpu": load_info["name"],
        "sm": load_info["sm"],
        "trainer": "sovereign_loop",
        "no_trl": True,
        "constitution": "oss.train.constitution",
    }
    (out_dir / "training_config.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    (out_dir / "sovereign_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8",
    )

    LOG.info("Sovereign train complete — %s loss=%.4f → %s", profile.agent_id, final_loss, out_dir)

    return TrainResult(
        agent_id=profile.agent_id,
        success=True,
        final_loss=final_loss,
        steps=stats["steps"],
        examples=len(examples),
        output_dir=str(out_dir),
        adapter_path=str(out_dir),
        gpu=load_info["name"],
        notes="sovereign_loop no_trl",
        loss_history=list(stats.get("loss_history", [])),
    )