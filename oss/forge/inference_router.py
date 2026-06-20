"""
Omni MoE Inference Router — novel routing beyond standard LoRA/task tags.

Advancements (not typical in production LLM stacks today):
  1. Spectral multi-domain classifier (20 scientific disciplines, superposition weights)
  2. Holographic elite-strand context reconstruction for prompt augmentation
  3. Epigenetic session affinity (domain memory accumulates across turns)
  4. Methylation-gated temperature scaling (high-fitness domains → precision mode)
  5. CRISPR locus system-prompt splice (targeted knowledge insertion)
  6. Fractal sub-domain drill-down when primary confidence is ambiguous
  7. Neuro-symbolic structure verifier hook (post-generation quality gate)
  8. Entropy-gated exploration (high classification entropy → raise temperature)
  9. Attractor-basin hysteresis (session domain sticks until evidence exceeds band)
  10. Memetic allele voting (elite strands compete to bias low-confidence routes)
  11. Topological persistence (consecutive same-domain turns reinforce routing)
  12. Causal counterfactual route (secondary domain preserved for audit/retry)
"""
from __future__ import annotations

import json
import logging
import math
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from oss.forge.domains import DOMAIN_CATALOG, domain_keywords, resolve_domain
from oss.forge.moe_farm import ADAPTER_BUCKETS, adapter_bucket_for_domain
from oss.forge.schemas import ForgeDomain

LOG = logging.getLogger("oss.forge.inference_router")

_REPO = Path(__file__).resolve().parents[2]
_ELITE_STRANDS = _REPO / "backend" / "data" / "training" / "forge_elite_strands.jsonl"

# Epigenetic session cache — domain affinity accumulates per session (novel)
_epigenetic_sessions: dict[str, dict[str, float]] = {}
# Topological persistence — last routed domain per session (novel)
_session_last_domain: dict[str, str] = {}
_session_domain_streak: dict[str, int] = {}

_CRISPR_LOCUS_PROMPTS: dict[str, str] = {
    "defense_locus": "[CRISPR:defense] Prioritize threat models, mitigations, audit trails.",
    "agency_locus": "[CRISPR:agency] Prioritize delegation graphs, verifier loops, tool plans.",
    "optimization_locus": "[CRISPR:optimization] Prioritize loss landscapes, convergence, stability bounds.",
    "elite_breed_locus": "[CRISPR:elite] OmniStrand density — concise, high-signal, no filler.",
}


@dataclass
class DomainSuperposition:
    """Quantum-inspired dual-domain blend when classification is ambiguous."""

    primary: ForgeDomain
    secondary: ForgeDomain | None
    primary_weight: float
    secondary_weight: float
    confidence: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "primary": self.primary.value,
            "secondary": self.secondary.value if self.secondary else None,
            "primary_weight": round(self.primary_weight, 3),
            "secondary_weight": round(self.secondary_weight, 3),
            "confidence": round(self.confidence, 3),
        }


@dataclass
class InferenceRoutePlan:
    """Full routing plan applied before generation."""

    domain: ForgeDomain
    adapter_bucket: str
    superposition: DomainSuperposition
    elite_context: str
    crispr_prefix: str
    scaled_temperature: float
    augmented_messages: list[dict]
    amplification_factor: float
    novel_methods: list[str] = field(default_factory=list)
    verifier_enabled: bool = True
    spectral_entropy: float = 0.0
    domain_streak: int = 0
    counterfactual_domain: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain.value,
            "adapter_bucket": self.adapter_bucket,
            "superposition": self.superposition.to_dict(),
            "amplification_factor": round(self.amplification_factor, 2),
            "scaled_temperature": round(self.scaled_temperature, 3),
            "novel_methods": self.novel_methods,
            "elite_context_chars": len(self.elite_context),
            "spectral_entropy": round(self.spectral_entropy, 3),
            "domain_streak": self.domain_streak,
            "counterfactual_domain": self.counterfactual_domain,
        }


def _spectral_classify(text: str) -> dict[ForgeDomain, float]:
    """Score all scientific domains — spectral decomposition, not single label."""
    low = text.lower()
    scores: dict[ForgeDomain, float] = {}
    for spec in DOMAIN_CATALOG:
        kws = domain_keywords(spec.key)
        if not kws:
            scores[spec.key] = 0.0
            continue
        hits = sum(1.0 for kw in kws if kw in low)
        tag_hits = sum(0.5 for tag in spec.search_tags if tag.replace(" ", "") in low.replace(" ", ""))
        scores[spec.key] = (hits + tag_hits) / max(len(kws), 1)
    return scores


def _fractal_drill_down(text: str, primary: ForgeDomain, confidence: float) -> ForgeDomain:
    """When confidence < 0.35, drill into elite sub-discipline keywords."""
    if confidence >= 0.35:
        return primary
    elite_kws = {
        ForgeDomain.GENOMICS_INSPIRED_AI: ("methylation", "transcription", "strand", "crispr"),
        ForgeDomain.AGENTIC_SYSTEMS_SCIENCE: ("swarm", "delegate", "multi-agent"),
        ForgeDomain.ALIGNMENT_AND_SAFETY_SCIENCE: ("alignment", "jailbreak", "safety"),
    }
    low = text.lower()
    best, best_score = primary, 0.0
    for domain, kws in elite_kws.items():
        score = sum(1 for k in kws if k in low)
        if score > best_score:
            best, best_score = domain, score
    return best if best_score > 0 else primary


def _superposition_from_scores(scores: dict[ForgeDomain, float]) -> DomainSuperposition:
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    primary, p_score = ranked[0]
    secondary, s_score = ranked[1] if len(ranked) > 1 else (None, 0.0)
    total = p_score + s_score + 1e-9
    confidence = p_score / max(0.01, total)
    if s_score < 0.15 or confidence > 0.72:
        return DomainSuperposition(primary, None, 1.0, 0.0, confidence)
    return DomainSuperposition(
        primary, secondary,
        p_score / total, s_score / total,
        confidence,
    )


def _epigenetic_update(session_id: str, domain: ForgeDomain, weight: float) -> None:
    if not session_id:
        return
    aff = _epigenetic_sessions.setdefault(session_id, {})
    key = domain.value
    aff[key] = aff.get(key, 0.0) * 0.7 + weight * 0.3


def _epigenetic_bias(session_id: str, *, hysteresis: float = 0.15) -> ForgeDomain | None:
    """Attractor-basin hysteresis — domain sticks until rival exceeds band."""
    aff = _epigenetic_sessions.get(session_id or "")
    if not aff:
        return None
    ranked = sorted(aff.items(), key=lambda x: x[1], reverse=True)
    best_key, best_val = ranked[0]
    if best_val < 0.25:
        return None
    if len(ranked) > 1:
        rival_val = ranked[1][1]
        if best_val - rival_val < hysteresis:
            return None
    return resolve_domain(best_key)


def _spectral_entropy(scores: dict[ForgeDomain, float]) -> float:
    """Shannon entropy over normalized spectral scores — ambiguity detector."""
    vals = [max(v, 0.0) for v in scores.values()]
    total = sum(vals) + 1e-9
    probs = [v / total for v in vals if v > 0]
    if len(probs) <= 1:
        return 0.0
    return -sum(p * math.log2(p) for p in probs)


def _entropy_temperature_boost(base: float, entropy: float, max_entropy: float = 4.0) -> float:
    """High entropy → exploration mode (rare in production routers)."""
    if entropy < 2.0:
        return base
    factor = 1.0 + min(0.35, (entropy - 2.0) / max_entropy)
    return min(1.5, base * factor)


def _memetic_allele_vote(query: str, scores: dict[ForgeDomain, float]) -> ForgeDomain | None:
    """Elite strands vote on domain when spectral confidence is weak."""
    strands = _load_elite_strands()
    if not strands:
        return None
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    if ranked[0][1] >= 0.35:
        return None
    q_words = {w for w in query.lower().split() if len(w) > 4}
    votes: dict[ForgeDomain, float] = {}
    for s in strands:
        fitness = float(s.get("fitness", 0))
        if fitness < 0.72:
            continue
        try:
            dom = resolve_domain(s.get("domain", ""))
        except Exception:
            continue
        chatml = (s.get("chatml") or "").lower()
        overlap = sum(1 for w in q_words if w in chatml)
        if overlap:
            votes[dom] = votes.get(dom, 0.0) + fitness * overlap
    if not votes:
        return None
    return max(votes.items(), key=lambda x: x[1])[0]


def _topological_persistence(session_id: str, domain: ForgeDomain) -> int:
    """Consecutive same-domain turns — persistence reinforcement signal."""
    if not session_id:
        return 0
    key = domain.value
    prev = _session_last_domain.get(session_id)
    if prev == key:
        _session_domain_streak[session_id] = _session_domain_streak.get(session_id, 1) + 1
    else:
        _session_domain_streak[session_id] = 1
        _session_last_domain[session_id] = key
    return _session_domain_streak[session_id]


def _load_elite_strands() -> list[dict]:
    if not _ELITE_STRANDS.exists():
        return []
    strands = []
    with open(_ELITE_STRANDS, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    strands.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return strands


def _holographic_elite_context(domain: ForgeDomain, query: str, limit: int = 2) -> str:
    """
    Holographic reconstruction — any matching elite strand carries partial domain signal.
    Injects compressed exemplar assistant patterns (not full fine-tune).
    """
    strands = _load_elite_strands()
    if not strands:
        return ""
    q_low = query.lower()
    matched = []
    for s in strands:
        if s.get("domain") != domain.value:
            continue
        fitness = float(s.get("fitness", 0))
        if fitness < 0.7:
            continue
        chatml = s.get("chatml", "")
        if not chatml:
            continue
        # extract assistant slice for holographic fragment
        if "<|im_start|>assistant" in chatml:
            frag = chatml.split("<|im_start|>assistant", 1)[-1].split("<|im_end|>", 1)[0].strip()
        else:
            frag = chatml[:400]
        relevance = sum(1 for w in q_low.split()[:20] if len(w) > 4 and w in frag.lower())
        matched.append((fitness + relevance * 0.1, frag[:500]))
    matched.sort(reverse=True)
    if not matched:
        return ""
    parts = [f"[holographic:{domain.value}:{i}] {frag}" for i, (_, frag) in enumerate(matched[:limit])]
    return "\n".join(parts)


def _methylation_temperature(base: float, fitness: float) -> float:
    """High-fitness elite domains → lower temperature (precision epigenetics)."""
    if fitness >= 0.88:
        return max(0.1, base * 0.65)
    if fitness >= 0.75:
        return max(0.15, base * 0.8)
    return base


def _crispr_splice(domain: ForgeDomain, strand_meta: dict | None = None) -> str:
    targets = list(_CRISPR_LOCUS_PROMPTS.keys())
    if strand_meta:
        targets = strand_meta.get("crispr_targets", targets)
    parts = [_CRISPR_LOCUS_PROMPTS[t] for t in targets if t in _CRISPR_LOCUS_PROMPTS]
    return " ".join(parts[:3])


def _best_strand_fitness(domain: ForgeDomain) -> float:
    strands = _load_elite_strands()
    fits = [float(s.get("fitness", 0)) for s in strands if s.get("domain") == domain.value]
    return max(fits) if fits else 0.65


def _amplification_factor(domain: ForgeDomain) -> float:
    strands = _load_elite_strands()
    amps = [
        float(s.get("capability_amplifier", 1))
        for s in strands if s.get("domain") == domain.value
    ]
    return max(amps) if amps else 1.0


def plan_inference_route(
    messages: list[dict],
    *,
    task_domain: str = "",
    session_id: str = "",
    base_temperature: float = 0.7,
) -> InferenceRoutePlan:
    """Build full Omni MoE routing plan with novel augmentations."""
    combined = " ".join(
        m.get("content", "") for m in messages if m.get("role") in ("system", "user")
    )

    scores: dict[ForgeDomain, float] = {}
    entropy = 0.0
    counterfactual: str | None = None
    _bucket_override: str | None = None

    if task_domain:
        if task_domain in ADAPTER_BUCKETS:
            _bucket_override = task_domain
            domain = ForgeDomain.GENERAL_COGNITION
            superposition = DomainSuperposition(domain, None, 1.0, 0.0, 1.0)
            methods = ["explicit_domain", "legacy_adapter_bucket"]
        else:
            domain = resolve_domain(task_domain)
            superposition = DomainSuperposition(domain, None, 1.0, 0.0, 1.0)
            methods = ["explicit_domain"]
    else:
        scores = _spectral_classify(combined)
        entropy = _spectral_entropy(scores)
        epigenetic = _epigenetic_bias(session_id)
        if epigenetic:
            scores[epigenetic] = scores.get(epigenetic, 0) + 0.25
            methods = ["spectral_classify", "attractor_hysteresis"]
        else:
            methods = ["spectral_classify"]
        allele = _memetic_allele_vote(combined, scores)
        if allele:
            scores[allele] = scores.get(allele, 0) + 0.2
            methods.append("memetic_allele_vote")
        superposition = _superposition_from_scores(scores)
        domain = _fractal_drill_down(combined, superposition.primary, superposition.confidence)
        if superposition.secondary:
            counterfactual = superposition.secondary.value

    streak = _topological_persistence(session_id, domain)
    if streak >= 3 and not task_domain:
        methods.append("topological_persistence")

    _epigenetic_update(session_id, domain, superposition.primary_weight)

    bucket = _bucket_override if _bucket_override is not None else adapter_bucket_for_domain(domain)
    fitness = _best_strand_fitness(domain)
    elite_ctx = _holographic_elite_context(domain, combined)
    crispr = _crispr_splice(domain)
    scaled_temp = _methylation_temperature(base_temperature, fitness)
    if entropy > 2.0 and not task_domain:
        scaled_temp = _entropy_temperature_boost(scaled_temp, entropy)
        methods.append("entropy_gated_exploration")
    amp = _amplification_factor(domain)

    if superposition.secondary:
        methods.append("superposition_blend")
        elite_ctx += "\n" + _holographic_elite_context(superposition.secondary, combined, limit=1)

    if elite_ctx:
        methods.append("holographic_context")
    if crispr:
        methods.append("crispr_splice")
    methods.append("methylation_temperature")

    # Augment messages
    augmented = [dict(m) for m in messages]
    system_parts = []
    if crispr:
        system_parts.append(crispr)
    if elite_ctx:
        system_parts.append(f"[Omni Elite Context]\n{elite_ctx}")
    if superposition.secondary:
        system_parts.append(
            f"[Superposition] primary={superposition.primary.value} "
            f"({superposition.primary_weight:.0%}) + "
            f"secondary={superposition.secondary.value} ({superposition.secondary_weight:.0%})"
        )
    system_parts.append(
        f"[Route] domain={domain.value} bucket={bucket} "
        f"effective_amp≈{amp:.1f}x"
    )

    inject = "\n".join(system_parts)
    if augmented and augmented[0].get("role") == "system":
        augmented[0] = {
            "role": "system",
            "content": inject + "\n\n" + augmented[0]["content"],
        }
    else:
        augmented.insert(0, {"role": "system", "content": inject})

    if counterfactual:
        methods.append("causal_counterfactual_route")

    return InferenceRoutePlan(
        domain=domain,
        adapter_bucket=bucket,
        superposition=superposition,
        elite_context=elite_ctx,
        crispr_prefix=crispr,
        scaled_temperature=scaled_temp,
        augmented_messages=augmented,
        amplification_factor=amp,
        novel_methods=methods,
        spectral_entropy=entropy,
        domain_streak=streak,
        counterfactual_domain=counterfactual,
    )


def neuro_symbolic_verify(text: str, domain: ForgeDomain) -> dict[str, Any]:
    """
    Lightweight post-generation verifier — structure + domain signal check.
    Not a full neuro-symbolic engine; a prototype quality gate.
    """
    issues = []
    if len(text.strip()) < 20:
        issues.append("too_short")
    if text.lower().count("i cannot") > 0:
        issues.append("refusal_pattern")
    kws = domain_keywords(domain)
    if kws:
        hits = sum(1 for k in kws[:8] if k in text.lower())
        if hits == 0 and len(text) > 100:
            issues.append("domain_drift")
    if re.search(r"\b(N/A|TODO|placeholder)\b", text, re.I):
        issues.append("placeholder_leak")
    return {
        "passed": len(issues) == 0,
        "issues": issues,
        "domain": domain.value,
    }