"""Training constitution — non-negotiable rules enforced in code, not comments."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

LOG = logging.getLogger("oss.train.constitution")

LOSS_FLOOR = 0.3
LOSS_CEILING = 10.0
BLOCKED_SM_MAJOR = 6  # P100 — too slow, resets on cloud pushes

RULES: tuple[str, ...] = (
    "RULE 1: Never cast LoRA adapters to fp16 after get_peft_model()",
    "RULE 2: gradient_checkpointing use_reentrant=False only",
    "RULE 3: Collapse detection — 0.3 < loss < 10 before save",
    "RULE 4: Local RTX 5050 / Blackwell only — no P100/Kaggle",
    "RULE 5: Train assistant tokens only — prompt masked with -100",
    "RULE 6: No TRL/SFTTrainer — sovereign loop owns the step",
)


@dataclass
class ConstitutionViolation(Exception):
    rule: str
    detail: str

    def __str__(self) -> str:
        return f"{self.rule}: {self.detail}"


def assert_gpu_allowed() -> dict[str, Any]:
    import torch

    if not torch.cuda.is_available():
        raise ConstitutionViolation("RULE 4", "CUDA required — local GPU training only")
    major, minor = torch.cuda.get_device_capability(0)
    name = torch.cuda.get_device_name(0)
    if major == BLOCKED_SM_MAJOR:
        raise ConstitutionViolation("RULE 4", f"P100 sm_{major}{minor} blocked — use RTX 5050")
    if major >= 12:
        ver = tuple(int(x) for x in torch.__version__.split(".")[:2])
        if ver < (2, 6):
            raise ConstitutionViolation(
                "RULE 4", f"Blackwell needs PyTorch >= 2.6, got {torch.__version__}"
            )
    return {"gpu": name, "sm": f"{major}{minor}", "pytorch": torch.__version__}


def assert_loss_healthy(loss: float, *, step: int = 0) -> None:
    if loss != loss:  # NaN
        raise ConstitutionViolation("RULE 3", f"NaN loss at step {step}")
    if loss <= 0.0:
        raise ConstitutionViolation(
            "RULE 3",
            f"Collapsed loss={loss:.4f} at step {step} — gradient updates skipped",
        )
    if loss > LOSS_CEILING:
        raise ConstitutionViolation(
            "RULE 3",
            f"Diverged loss={loss:.4f} at step {step} — check lr/dataset",
        )


def assert_final_loss(loss: float) -> None:
    if not (LOSS_FLOOR < loss < LOSS_CEILING):
        raise ConstitutionViolation(
            "RULE 3",
            f"Final loss {loss:.4f} outside ({LOSS_FLOOR}, {LOSS_CEILING}) — adapter not saved",
        )


def audit_no_adapter_fp16_cast(model: Any) -> None:
    """RULE 1 — adapters must stay fp32 master weights under AMP."""
    import torch

    for name, param in model.named_parameters():
        if not param.requires_grad:
            continue
        if "lora" in name.lower() and param.dtype == torch.float16:
            raise ConstitutionViolation(
                "RULE 1",
                f"LoRA param {name} is fp16 — remove manual .to(fp16) casts",
            )


def checkpointing_kwargs() -> dict:
    return {"use_reentrant": False}


def constitution_report() -> dict[str, Any]:
    report: dict[str, Any] = {"rules": list(RULES), "checks": {}}
    try:
        import torch
        report["checks"]["torch"] = "ok"
        for pkg in ("peft", "transformers", "bitsandbytes"):
            try:
                __import__(pkg)
                report["checks"][pkg] = "ok"
            except ImportError:
                report["checks"][pkg] = "missing"
        if torch.cuda.is_available():
            report["checks"]["gpu"] = assert_gpu_allowed()
        else:
            report["checks"]["gpu"] = "cpu_only"
        report["ready"] = (
            report["checks"].get("torch") == "ok"
            and report["checks"].get("peft") == "ok"
            and report["checks"].get("gpu") != "cpu_only"
            and isinstance(report["checks"].get("gpu"), dict)
        )
    except ConstitutionViolation as exc:
        report["ready"] = False
        report["error"] = str(exc)
    except Exception as exc:
        report["ready"] = False
        report["error"] = str(exc)
    return report