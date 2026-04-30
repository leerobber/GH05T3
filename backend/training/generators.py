"""
Training data generators — uses Groq free tier + local Ollama.
Zero API cost. Runs overnight using GH05T3's own LLM routing.

Produces JSONL in formats ready for Qwen2.5-Coder fine-tuning.
"""
from __future__ import annotations

import json
import logging
import random
from pathlib import Path
from typing import AsyncGenerator

LOG = logging.getLogger("ghost.training.generators")

OUT_DIR = Path(__file__).parent / "datasets"
OUT_DIR.mkdir(exist_ok=True)


# ─────────────────────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────────────────────
async def _llm(system: str, user: str) -> str:
    """
    Hybrid routing for training generation:
      - TRAIN_USE_ANTHROPIC=1 + ANTHROPIC_API_KEY set → use Claude (fastest, best quality)
      - Otherwise → Groq free tier → Google free → local Ollama (zero cost)
    Set TRAIN_USE_ANTHROPIC=1 when you want maximum speed and have credits.
    Leave unset for fully free overnight generation.
    """
    if os.environ.get("TRAIN_USE_ANTHROPIC") == "1":
        from ghost_llm import _call_anthropic, nightly_chat
        ak = os.environ.get("ANTHROPIC_API_KEY", "")
        if ak:
            try:
                text = await _call_anthropic(system, user)
                return text.strip()
            except Exception as e:
                LOG.debug("anthropic failed, falling back to free: %s", e)
    from ghost_llm import nightly_chat
    text, _ = await nightly_chat("training", system, user)
    return text.strip()


def _write(path: Path, record: dict):
    with open(path, "a") as f:
        f.write(json.dumps(record) + "\n")


def _count(path: Path) -> int:
    if not path.exists():
        return 0
    with open(path) as f:
        return sum(1 for line in f if line.strip())


# ─────────────────────────────────────────────────────────────
# Dataset 1 — Adversarial Defense  (~5,000 examples)
# ─────────────────────────────────────────────────────────────
DEFENSE_SYS = """You are a defensive security expert generating training data.
Given a threat vector, produce a JSON object with exactly these fields:
{
  "threat_vector": "...",
  "exploitation_method": "brief technical description of how attacker exploits this",
  "detection_pattern": "specific log entries, anomalies, or indicators to detect this",
  "mitigation_strategy": "concrete defensive countermeasure to prevent or stop this"
}
Respond with valid JSON only. No explanation. Focus on detection and defense, never on weaponization."""

_THREAT_SEEDS = [
    "SQL injection via login form",
    "XSS reflected attack on search parameter",
    "SSRF via URL parameter in image fetcher",
    "Path traversal in file download endpoint",
    "Broken object level authorization in REST API",
    "JWT algorithm confusion attack",
    "LDAP injection in authentication",
    "XML external entity injection",
    "Command injection via filename parameter",
    "Insecure deserialization in session cookie",
    "Open redirect via callback URL",
    "CSRF on state-changing API endpoint",
    "Subdomain takeover via dangling CNAME",
    "HTTP request smuggling",
    "GraphQL introspection abuse",
    "Rate limiting bypass via IP rotation",
    "Mass assignment vulnerability in ORM",
    "Insecure direct object reference in profile endpoint",
    "SSTI in Jinja2 template engine",
    "DNS rebinding attack on localhost services",
    "Prototype pollution in JavaScript",
    "ReDoS via malicious regex input",
    "Account enumeration via timing difference",
    "Password reset token predictability",
    "Clickjacking via iframe embedding",
    "Cache poisoning via unkeyed header",
    "Business logic flaw in coupon redemption",
    "Information disclosure via verbose error",
    "Weak cryptographic key generation",
    "Session fixation after login",
]


async def generate_adversarial_defense(
    target: int = 5000,
    nvd_records: list[dict] | None = None,
    mitre_records: list[dict] | None = None,
) -> int:
    out = OUT_DIR / "adversarial_defense.jsonl"
    existing = _count(out)
    if existing >= target:
        LOG.info("adversarial_defense already at %d/%d", existing, target)
        return existing

    seeds = list(_THREAT_SEEDS)

    # Enrich seeds from NVD descriptions
    for rec in (nvd_records or [])[:500]:
        desc = rec.get("description", "")
        if desc and len(desc) > 40:
            seeds.append(desc[:200])

    # Enrich seeds from MITRE ATT&CK techniques
    for rec in (mitre_records or [])[:200]:
        name = rec.get("name", "")
        if name:
            seeds.append(f"ATT&CK technique: {name}")

    generated = existing
    random.shuffle(seeds)
    seed_cycle = (seeds * ((target // len(seeds)) + 2))[:target]

    for i, seed in enumerate(seed_cycle[existing:], start=existing + 1):
        try:
            raw = await _llm(DEFENSE_SYS, f"Threat vector: {seed}")
            # extract JSON even if wrapped in markdown
            start = raw.find("{")
            end   = raw.rfind("}") + 1
            if start == -1 or end == 0:
                continue
            obj = json.loads(raw[start:end])
            required = {"threat_vector", "exploitation_method",
                        "detection_pattern", "mitigation_strategy"}
            if not required.issubset(obj.keys()):
                continue
            _write(out, obj)
            generated += 1
            if generated % 100 == 0:
                LOG.info("adversarial_defense: %d/%d", generated, target)
        except Exception as e:
            LOG.debug("adversarial_defense gen error: %s", e)

    LOG.info("adversarial_defense complete: %d examples", generated)
    return generated


# ─────────────────────────────────────────────────────────────
# Dataset 2 — Multi-turn Reasoning Chains  (~3,000 examples)
# ─────────────────────────────────────────────────────────────
REASONING_SYS = """You are generating reasoning chain training data for an AI agent.
Given a question, produce a JSON object with exactly these fields:
{
  "question": "...",
  "reasoning_steps": ["step 1", "step 2", "step 3", "step 4", "step 5"],
  "data_sources": ["what information or evidence was considered"],
  "synthesis": "how the steps combine to reach the answer",
  "final_answer": "concise conclusion"
}
Respond with valid JSON only. Make reasoning explicit, auditable, and step-by-step."""

_REASONING_SEEDS = [
    "Why did the authentication system choose rate limiting over CAPTCHA?",
    "How should an AI agent decide between two conflicting security policies?",
    "What is the safest way to store API keys in a distributed system?",
    "Why might an anomaly detection system produce false positives?",
    "How do you determine if a system vulnerability is critical enough to patch immediately?",
    "What factors should influence the choice of encryption algorithm?",
    "Why is defense-in-depth more effective than perimeter-only security?",
    "How should a security agent prioritize incidents during a multi-vector attack?",
    "What makes a bug bounty report valid vs invalid?",
    "How does an attacker enumerate valid usernames without triggering alerts?",
    "Why is input validation at the server side necessary even with client-side checks?",
    "What signals indicate a system is being used as a pivot point in an attack?",
    "How does a security agent determine attribution for an attack?",
    "Why should secrets be rotated on a schedule rather than only after compromise?",
    "How do you evaluate whether a third-party library introduces supply chain risk?",
    "What reasoning process identifies a zero-day from behavioral anomalies?",
    "Why is least privilege important and how is it violated in practice?",
    "How should a system respond to an authenticated user performing unusual bulk exports?",
    "What evidence distinguishes a security researcher from a malicious actor?",
    "How does threat modeling change risk prioritization decisions?",
]


async def generate_reasoning_chains(
    target: int = 3000,
    hf_records: list[dict] | None = None,
) -> int:
    out = OUT_DIR / "reasoning_chains.jsonl"
    existing = _count(out)
    if existing >= target:
        LOG.info("reasoning_chains already at %d/%d", existing, target)
        return existing

    seeds = list(_REASONING_SEEDS)

    # Use HF examples as question seeds
    for rec in (hf_records or [])[:300]:
        q = rec.get("question", "")
        if q and len(q) > 20:
            seeds.append(q[:300])

    generated = existing
    seed_cycle = (seeds * ((target // len(seeds)) + 2))[:target]

    for seed in seed_cycle[existing:]:
        try:
            raw = await _llm(REASONING_SYS, f"Question: {seed}")
            start = raw.find("{")
            end   = raw.rfind("}") + 1
            if start == -1 or end == 0:
                continue
            obj = json.loads(raw[start:end])
            required = {"question", "reasoning_steps", "data_sources",
                        "synthesis", "final_answer"}
            if not required.issubset(obj.keys()):
                continue
            if not isinstance(obj["reasoning_steps"], list):
                continue
            _write(out, obj)
            generated += 1
            if generated % 100 == 0:
                LOG.info("reasoning_chains: %d/%d", generated, target)
        except Exception as e:
            LOG.debug("reasoning_chains gen error: %s", e)

    LOG.info("reasoning_chains complete: %d examples", generated)
    return generated


# ─────────────────────────────────────────────────────────────
# Dataset 3 — CVE Pattern Analysis  (~3,000 examples)
# ─────────────────────────────────────────────────────────────
CVE_SYS = """You are a security analyst generating training data about vulnerability patterns.
Given a CVE description, produce a JSON object with exactly these fields:
{
  "vulnerability_pattern": "abstract pattern this CVE represents (e.g. 'buffer overflow in parsing')",
  "discovery_indicators": ["observable signs that this class of vulnerability exists"],
  "exploitation_timeline": "typical time from discovery to weaponization for this pattern",
  "defensive_lessons": "what defenders should implement to prevent this class of issue"
}
Respond with valid JSON only. Focus on pattern recognition and defense, not exploitation."""


async def generate_cve_patterns(
    target: int = 3000,
    nvd_records: list[dict] | None = None,
) -> int:
    out = OUT_DIR / "cve_patterns.jsonl"
    existing = _count(out)
    if existing >= target:
        LOG.info("cve_patterns already at %d/%d", existing, target)
        return existing

    records = [r for r in (nvd_records or []) if r.get("description") and len(r["description"]) > 60]
    if not records:
        LOG.warning("no NVD records for cve_patterns — collect NVD data first")
        return existing

    random.shuffle(records)
    generated = existing

    for rec in records[existing:existing + (target - existing)]:
        try:
            desc = rec["description"][:600]
            cve_id = rec.get("cve_id", "unknown")
            prompt = f"CVE ID: {cve_id}\nDescription: {desc}"
            raw = await _llm(CVE_SYS, prompt)
            start = raw.find("{")
            end   = raw.rfind("}") + 1
            if start == -1 or end == 0:
                continue
            obj = json.loads(raw[start:end])
            required = {"vulnerability_pattern", "discovery_indicators",
                        "exploitation_timeline", "defensive_lessons"}
            if not required.issubset(obj.keys()):
                continue
            obj["source_cve"] = cve_id
            obj["cvss_score"]  = rec.get("cvss_score", 0)
            _write(out, obj)
            generated += 1
            if generated % 100 == 0:
                LOG.info("cve_patterns: %d/%d", generated, target)
        except Exception as e:
            LOG.debug("cve_patterns gen error: %s", e)

    LOG.info("cve_patterns complete: %d examples", generated)
    return generated


# ─────────────────────────────────────────────────────────────
# Dataset 4 — Bug Bounty Methodologies  (~5,000 examples)
# Scaled back from 12,000 to what's realistic free/local
# ─────────────────────────────────────────────────────────────
BOUNTY_SYS = """You are a security researcher generating ethical bug bounty training data.
Given a target system type and vulnerability class, produce a JSON object:
{
  "target_system": "type of system (e.g. REST API, web app, mobile app)",
  "recon_method": "passive or non-intrusive discovery technique",
  "vulnerability_found": "specific vulnerability class and location",
  "non_weaponized_poc": "proof of concept that ONLY demonstrates existence, not exploitation",
  "impact_assessment": "business impact if this were exploited",
  "remediation": "specific code-level or configuration fix"
}
All examples must be from a defensive/researcher perspective.
Respond with valid JSON only."""

_BOUNTY_SEEDS = [
    ("REST API", "IDOR on user profile endpoint"),
    ("web application", "stored XSS in comment field"),
    ("mobile app", "insecure data storage in local database"),
    ("GraphQL API", "introspection revealing sensitive schema"),
    ("OAuth flow", "state parameter missing CSRF protection"),
    ("file upload endpoint", "unrestricted file type allowing SSRF"),
    ("admin panel", "broken access control on user management"),
    ("password reset flow", "token reuse after password change"),
    ("API gateway", "rate limiting absent on authentication endpoint"),
    ("webhook handler", "SSRF via controllable callback URL"),
    ("email verification", "link still valid after email change"),
    ("payment form", "amount parameter tampering in checkout"),
    ("search functionality", "SQL injection via sort parameter"),
    ("image processing", "SSRF via image URL fetch"),
    ("export feature", "path traversal in filename parameter"),
    ("user settings", "account takeover via email change without verification"),
    ("API versioning", "old API version bypasses new auth controls"),
    ("CDN configuration", "cache poisoning via unkeyed Host header"),
    ("session management", "session not invalidated after logout"),
    ("debug endpoint", "stack trace leaking internal paths in production"),
]


async def generate_bug_bounty(
    target: int = 5000,
    mitre_records: list[dict] | None = None,
) -> int:
    out = OUT_DIR / "bug_bounty.jsonl"
    existing = _count(out)
    if existing >= target:
        LOG.info("bug_bounty already at %d/%d", existing, target)
        return existing

    seeds = list(_BOUNTY_SEEDS)

    # Generate additional seeds from MITRE techniques
    for rec in (mitre_records or [])[:100]:
        name = rec.get("name", "")
        tactics = rec.get("tactics", [])
        if name and "web" in " ".join(tactics).lower():
            seeds.append(("web application", name))

    generated = existing
    seed_cycle = (seeds * ((target // len(seeds)) + 2))[:target]

    for target_sys, vuln_class in seed_cycle[existing:]:
        try:
            prompt = f"Target system: {target_sys}\nVulnerability class: {vuln_class}"
            raw = await _llm(BOUNTY_SYS, prompt)
            start = raw.find("{")
            end   = raw.rfind("}") + 1
            if start == -1 or end == 0:
                continue
            obj = json.loads(raw[start:end])
            required = {"target_system", "recon_method", "vulnerability_found",
                        "non_weaponized_poc", "impact_assessment", "remediation"}
            if not required.issubset(obj.keys()):
                continue
            _write(out, obj)
            generated += 1
            if generated % 100 == 0:
                LOG.info("bug_bounty: %d/%d", generated, target)
        except Exception as e:
            LOG.debug("bug_bounty gen error: %s", e)

    LOG.info("bug_bounty complete: %d examples", generated)
    return generated


# ─────────────────────────────────────────────────────────────
# Dataset stats
# ─────────────────────────────────────────────────────────────
def dataset_stats() -> dict:
    stats = {}
    for p in OUT_DIR.glob("*.jsonl"):
        stats[p.stem] = _count(p)
    return stats
