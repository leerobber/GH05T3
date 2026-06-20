"""Scientific domain → adapter bucket mapping for MoE inference."""
from __future__ import annotations

from pathlib import Path

from oss.forge.schemas import ForgeDomain

# Scientific domain → physical adapter directory name
SCIENTIFIC_ADAPTER_DIRS: dict[ForgeDomain, str] = {
    ForgeDomain.CYBER_DEFENSE_SCIENCE: "security_adapter",
    ForgeDomain.COMPUTATIONAL_SCIENCE: "code_adapter",
    ForgeDomain.EPISTEMOLOGY_AND_DISCOVERY: "research_adapter",
    ForgeDomain.SYSTEMS_ENGINEERING: "ops_adapter",
    ForgeDomain.STATISTICAL_INFERENCE_SCIENCE: "research_adapter",
    ForgeDomain.THEORETICAL_COMPUTER_SCIENCE: "code_adapter",
    ForgeDomain.MYCOLOGICAL_NETWORK_ECONOMICS: "ops_adapter",
    ForgeDomain.THEORETICAL_PHYSICS_AND_COMPLEXITY: "research_adapter",
    ForgeDomain.FRONTIER_UNKNOWN_SCIENCES: "gh05t3_lora_adapter",
    ForgeDomain.GENERAL_COGNITION: "gh05t3_lora_adapter",
    # Elite AI/ML → research/code buckets until dedicated adapters train
    ForgeDomain.MACHINE_LEARNING_THEORY: "research_adapter",
    ForgeDomain.DEEP_LEARNING_ARCHITECTURES: "code_adapter",
    ForgeDomain.NEURAL_SYMBOLIC_INTEGRATION: "research_adapter",
    ForgeDomain.EVOLUTIONARY_COMPUTATION: "research_adapter",
    ForgeDomain.GENOMICS_INSPIRED_AI: "research_adapter",
    ForgeDomain.COGNITIVE_NEUROSCIENCE: "research_adapter",
    ForgeDomain.QUANTUM_MACHINE_LEARNING: "research_adapter",
    ForgeDomain.ALIGNMENT_AND_SAFETY_SCIENCE: "security_adapter",
    ForgeDomain.MULTIMODAL_REPRESENTATION_LEARNING: "code_adapter",
    ForgeDomain.AGENTIC_SYSTEMS_SCIENCE: "ops_adapter",
}

# Legacy bucket names for vLLM LoRA farm compatibility
ADAPTER_BUCKETS: dict[str, str] = {
    "business": "domain_research_adapter",
    "security": "security_adapter",
    "code": "code_adapter",
    "research": "research_adapter",
    "ops": "ops_adapter",
    "quick": "gh05t3_lora_adapter",
    "default": "gh05t3_lora_adapter",
}


def adapter_bucket_for_domain(domain: ForgeDomain) -> str:
    """Map scientific domain to legacy LoRA bucket."""
    subdir = SCIENTIFIC_ADAPTER_DIRS.get(domain, "gh05t3_lora_adapter")
    for bucket, path in ADAPTER_BUCKETS.items():
        if path == subdir:
            return bucket
    return "default"


def resolve_adapter_path(base_dir: Path, domain: ForgeDomain) -> tuple[str, Path]:
    """Return (bucket_name, adapter_path) with fallback to default."""
    subdir = SCIENTIFIC_ADAPTER_DIRS.get(domain, "gh05t3_lora_adapter")
    path = base_dir / subdir
    if not (path / "adapter_config.json").exists():
        # nested layout from training output
        nested = path / subdir
        if (nested / "adapter_config.json").exists():
            return adapter_bucket_for_domain(domain), nested
        default = base_dir / "gh05t3_lora_adapter"
        nested_default = default / "gh05t3_lora_adapter"
        if (nested_default / "adapter_config.json").exists():
            return "default", nested_default
        if (default / "adapter_config.json").exists():
            return "default", default
        return "default", default
    return adapter_bucket_for_domain(domain), path


_ROLE_BUCKETS: dict[str, str] = {
    "builder": "business",
    "investor": "business",
    "scientist": "research",
    "operator": "ops",
    "governor": "security",
}


def adapter_dir_for_bucket(bucket: str) -> str:
    return ADAPTER_BUCKETS.get(bucket, ADAPTER_BUCKETS["default"])


def adapter_bucket_for_agent_role(role: str) -> str:
    return _ROLE_BUCKETS.get(role.lower(), "default")


def resolve_legacy_adapter_bucket(bucket: str) -> str:
    return bucket if bucket in ADAPTER_BUCKETS else "default"


def resolve_adapter_path_for_bucket(base_dir: Path, bucket: str) -> tuple[str, Path]:
    subdir = adapter_dir_for_bucket(bucket)
    path = base_dir / subdir
    if not (path / "adapter_config.json").exists():
        nested = path / subdir
        if (nested / "adapter_config.json").exists():
            return bucket, nested
        default = base_dir / ADAPTER_BUCKETS["default"]
        if (default / "adapter_config.json").exists():
            return "default", default
        return "default", default
    return bucket, path


def list_moe_status(base_dir: Path) -> dict:
    """Report which scientific domains have trained adapters on disk."""
    status: dict[str, dict] = {}
    for domain, subdir in SCIENTIFIC_ADAPTER_DIRS.items():
        path = base_dir / subdir
        has_config = (path / "adapter_config.json").exists() or (
            (path / subdir / "adapter_config.json").exists()
        )
        status[domain.value] = {
            "adapter_dir": subdir,
            "trained": has_config,
            "bucket": adapter_bucket_for_domain(domain),
        }
    return status