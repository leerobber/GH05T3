"""Multi-signal quality gate — filters trash, promotes gold training shards."""
from __future__ import annotations

import hashlib
import re
from collections import Counter

from oss.forge.schemas import ForgeDomain, QualityTier, QualityVerdict, TrainingShard

_JUNK_PATTERNS = (
    r"lorem ipsum",
    r"as an ai language model",
    r"i cannot help",
    r"placeholder",
    r"todo:? fix",
    r"xxx+",
    r"test test test",
    r"^\s*N/A\s*$",
)

_DOMAIN_KEYWORDS: dict[ForgeDomain, tuple[str, ...]] = {
    ForgeDomain.SECURITY: ("cve", "exploit", "mitigation", "threat", "vulnerability", "owasp"),
    ForgeDomain.CODE: ("function", "class", "refactor", "debug", "api", "algorithm", "python"),
    ForgeDomain.RESEARCH: ("hypothesis", "methodology", "literature", "synthesis", "evidence"),
    ForgeDomain.OPS: ("deploy", "incident", "runbook", "sla", "capacity", "rollback"),
    ForgeDomain.DATA_SCIENCE: ("feature", "model", "bias", "variance", "dataset", "regression", "cluster"),
    ForgeDomain.COMPUTER_SCIENCE: ("complexity", "compiler", "distributed", "cache", "protocol", "graph"),
    ForgeDomain.FUNGI_ECONOMICS: ("mycelium", "network", "resource", "exchange", "symbiosis", "allocation"),
    ForgeDomain.THEORETICAL_SCIENCE: ("theorem", "entropy", "field", "symmetry", "quantum", "emergence"),
    ForgeDomain.UNKNOWN: ("uncertainty", "frontier", "unknown", "explore", "epistemic", "anomaly"),
}


def _word_stats(text: str) -> tuple[int, float, float]:
    words = re.findall(r"[a-zA-Z]{3,}", text.lower())
    if not words:
        return 0, 0.0, 0.0
    counts = Counter(words)
    unique_ratio = len(counts) / len(words)
    top_share = counts.most_common(1)[0][1] / len(words) if words else 1.0
    return len(words), unique_ratio, top_share


def _domain_relevance(shard: TrainingShard) -> float:
    blob = f"{shard.user} {shard.assistant}".lower()
    keywords = _DOMAIN_KEYWORDS.get(shard.domain, ())
    if not keywords:
        return 0.5
    hits = sum(1 for kw in keywords if kw in blob)
    return min(1.0, hits / max(3, len(keywords) * 0.4))


def _structure_score(text: str) -> float:
    score = 0.0
    if re.search(r"\d+\.\s", text):
        score += 0.25
    if "**" in text or "##" in text:
        score += 0.2
    if "```" in text:
        score += 0.2
    if len(re.findall(r"\n\n", text)) >= 1:
        score += 0.15
    if re.search(r"(because|therefore|however|consequently)", text, re.I):
        score += 0.2
    return min(1.0, score)


def _junk_hits(text: str) -> list[str]:
    reasons = []
    low = text.lower()
    for pat in _JUNK_PATTERNS:
        if re.search(pat, low, re.I | re.MULTILINE):
            reasons.append(f"junk_pattern:{pat[:24]}")
    na_ratio = low.count("n/a") / max(1, len(low.split()))
    if na_ratio > 0.08:
        reasons.append("excessive_na")
    if len(text.strip()) < 80:
        reasons.append("too_short")
    if len(text) > 12000:
        reasons.append("too_long")
    url_count = len(re.findall(r"https?://", text))
    if url_count > 8:
        reasons.append("url_spam")
    return reasons


def score_shard(shard: TrainingShard, min_tier: QualityTier = QualityTier.SILVER) -> QualityVerdict:
    """Score a shard; trash tier is rejected from training export."""
    combined = f"{shard.user}\n{shard.assistant}"
    reasons = _junk_hits(combined)

    words, unique_ratio, top_share = _word_stats(combined)
    domain_rel = _domain_relevance(shard)
    structure = _structure_score(shard.assistant)
    completeness = min(1.0, words / 120)
    repetition_penalty = max(0.0, 1.0 - top_share * 2)

    signals = {
        "completeness": completeness,
        "unique_ratio": unique_ratio,
        "repetition": repetition_penalty,
        "domain_relevance": domain_rel,
        "structure": structure,
    }

    if reasons:
        raw = sum(signals.values()) / len(signals) * 0.35
    else:
        raw = (
            signals["completeness"] * 0.15
            + signals["unique_ratio"] * 0.2
            + signals["repetition"] * 0.15
            + signals["domain_relevance"] * 0.25
            + signals["structure"] * 0.25
        )

    if shard.metadata.get("curated_seed"):
        raw = min(1.0, raw + 0.15)
    elif shard.metadata.get("quality_boost"):
        raw = min(1.0, raw + float(shard.metadata["quality_boost"]))

    score = round(max(0.0, min(1.0, raw)), 4)

    if score >= 0.88 and not reasons:
        tier = QualityTier.PLATINUM
    elif score >= 0.75:
        tier = QualityTier.GOLD
    elif score >= 0.6:
        tier = QualityTier.SILVER
    elif score >= 0.4:
        tier = QualityTier.BRONZE
    else:
        tier = QualityTier.TRASH

    if any(r.startswith("junk_pattern") or r in ("too_short", "url_spam", "excessive_na") for r in reasons):
        tier = QualityTier.TRASH

    tier_order = [QualityTier.TRASH, QualityTier.BRONZE, QualityTier.SILVER, QualityTier.GOLD, QualityTier.PLATINUM]
    keep = tier_order.index(tier) >= tier_order.index(min_tier)

    return QualityVerdict(score=score, tier=tier, signals=signals, reasons=reasons, keep=keep)


def content_hash(shard: TrainingShard) -> str:
    body = f"{shard.domain.value}|{shard.user}|{shard.assistant}".strip().lower()
    return hashlib.sha256(body.encode()).hexdigest()