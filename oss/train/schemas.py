"""Sovereign Train job schemas."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class TrainSource(str, Enum):
    FORGE = "forge"
    ELITE = "elite"
    AGENT_FILES = "agent_files"
    ALL = "all"


@dataclass
class TrainConfig:
    model_id: str = "Qwen/Qwen2.5-Coder-3B-Instruct"
    lora_rank: int = 16
    lora_alpha: int = 32
    max_steps: int = 500
    learning_rate: float = 2e-5
    max_grad_norm: float = 0.3
    batch_size: int = 1
    grad_accum: int = 8
    max_seq_len: int = 1024
    warmup_steps: int = 50
    load_4bit: bool = True
    gpu_memory_frac: float = 0.70
    seed: int = 42
    log_every: int = 10
    sources: list[TrainSource] = field(
        default_factory=lambda: [TrainSource.FORGE, TrainSource.ELITE]
    )

    def resolved_warmup(self) -> int:
        return min(self.warmup_steps, max(5, self.max_steps // 5))


@dataclass
class TrainJob:
    agent_id: str = "GH05T3"
    config: TrainConfig = field(default_factory=TrainConfig)
    output_dir: Path | None = None
    dry_run: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "output_dir": str(self.output_dir) if self.output_dir else None,
            "dry_run": self.dry_run,
            "config": {
                "model_id": self.config.model_id,
                "max_steps": self.config.max_steps,
                "sources": [s.value for s in self.config.sources],
            },
        }


@dataclass
class TrainResult:
    agent_id: str
    success: bool
    final_loss: float
    steps: int
    examples: int
    output_dir: str
    adapter_path: str
    paradigm: str = "sovereign_omni_strand"
    gpu: str = ""
    notes: str = ""
    loss_history: list[float] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "success": self.success,
            "final_loss": round(self.final_loss, 4),
            "steps": self.steps,
            "examples": self.examples,
            "output_dir": self.output_dir,
            "adapter_path": self.adapter_path,
            "paradigm": self.paradigm,
            "gpu": self.gpu,
            "notes": self.notes,
            "loss_history": [round(x, 4) for x in self.loss_history[-20:]],
        }