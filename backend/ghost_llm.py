"""LLM helpers — native multi-provider router, zero third-party SDK wrapper.

Premium / chat path  (Anthropic-first, falls back through free tiers):
    1. Anthropic Claude  (ANTHROPIC_API_KEY)
    2. Groq free tier    (GROQ_API_KEY)        — llama-3.3-70b-versatile
    3. Google Gemini     (GOOGLE_AI_KEY)        — gemini-2.0-flash
    4. Ollama            (OLLAMA_GATEWAY_URL)   — local, completely free

Cost-free / nightly path  (cheapest first):
    1. Ollama            — local, free
    2. Groq free tier    (GROQ_API_KEY)
    3. Google Gemini     (GOOGLE_AI_KEY)
    4. Anthropic         (ANTHROPIC_API_KEY)   — only if key present

Set LLM_PROVIDER=ollama to force Ollama for all calls.
"""
from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

from ollama_gateway import call as ollama_call, resolved_url as ollama_resolved_url
from ollama_gateway import PREFERRED as OLLAMA_PREFERRED

LOG = logging.getLogger("ghost.llm")

LLM_PROVIDER    = os.environ.get("LLM_PROVIDER",    "anthropic")
LLM_MODEL       = os.environ.get("LLM_MODEL",       "claude-sonnet-4-6")
ANTHROPIC_MODEL = os.environ.get("LLM_MODEL",       "claude-sonnet-4-6")


# ---------------------------------------------------------------------------
# Error types
# ---------------------------------------------------------------------------
class NoLLMError(RuntimeError):
    """No LLM provider is configured or all configured providers failed."""


# ---------------------------------------------------------------------------
# Nightly config (persisted in Mongo, overridable via API)
# ---------------------------------------------------------------------------
_DB_REF: dict = {"db": None}


def bind_db(db) -> None:
    _DB_REF["db"] = db


async def get_nightly_config() -> dict:
    db = _DB_REF["db"]
    if db is None:
        return {}
    doc = await db.llm_config.find_one({"_id": "nightly"}, {"_id": 0})
    return doc or {}


async def set_nightly_config(cfg: dict) -> dict:
    db = _DB_REF["db"]
    cfg = {k: v for k, v in cfg.items() if v is not None}
    await db.llm_config.update_one(
        {"_id": "nightly"}, {"$set": cfg}, upsert=True,
    )
    return await get_nightly_config()


# ---------------------------------------------------------------------------
# Native provider calls — no wrappers
# ---------------------------------------------------------------------------
async def _call_anthropic(system: str, user: str, model: str | None = None) -> str:
    import anthropic  # in requirements.txt
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    client = anthropic.AsyncAnthropic(api_key=key)
    kwargs: dict = {
        "model": model or ANTHROPIC_MODEL,
        "max_tokens": 4096,
        "messages": [{"role": "user", "content": user}],
    }
    if system:
        kwargs["system"] = system
    resp = await client.messages.create(**kwargs)
    return resp.content[0].text


async def _call_groq(system: str, user: str,
                     model: str = "llama-3.3-70b-versatile",
                     api_key: str | None = None) -> str:
    key = api_key or os.environ.get("GROQ_API_KEY", "")
    if not key:
        raise RuntimeError("GROQ_API_KEY not set")
    return await _openai_compat(
        "https://api.groq.com/openai/v1", key, model, system, user,
    )


async def _call_google(system: str, user: str,
                       model: str = "gemini-2.0-flash",
                       api_key: str | None = None) -> str:
    key = api_key or os.environ.get("GOOGLE_AI_KEY", "")
    if not key:
        raise RuntimeError("GOOGLE_AI_KEY not set")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {"temperature": 0.6, "maxOutputTokens": 1024},
    }
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(url, json=body)
        r.raise_for_status()
        j = r.json()
        try:
            return j["candidates"][0]["content"]["parts"][0]["text"]
        except Exception:
            return json.dumps(j)[:500]


async def _openai_compat(base: str, api_key: str | None,
                         model: str, system: str, user: str) -> str:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(
            f"{base.rstrip('/')}/chat/completions",
            headers=headers,
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user",   "content": user},
                ],
                "temperature": 0.6,
            },
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


# ---------------------------------------------------------------------------
# Availability helpers
# ---------------------------------------------------------------------------
async def ollama_available() -> bool:
    url = ollama_resolved_url()
    if not url:
        return False
    try:
        async with httpx.AsyncClient(timeout=2.0) as c:
            r = await c.get(f"{url}/v1/models")
            return r.status_code == 200
    except Exception:
        return False


def _anthropic_key() -> str:
    return os.environ.get("ANTHROPIC_API_KEY", "")


def _groq_key() -> str:
    return os.environ.get("GROQ_API_KEY", "")


def _google_key() -> str:
    return os.environ.get("GOOGLE_AI_KEY", "")


# ---------------------------------------------------------------------------
# Public chat functions
# ---------------------------------------------------------------------------
async def chat_once(session: str, system: str, user: str,
                    role: str = "proposer") -> tuple[str, str]:
    """Premium path: Anthropic → Groq → Google → Ollama.

    Forces Ollama only when LLM_PROVIDER=='ollama' to protect the GPU
    from being hit during normal chat.
    """
    if LLM_PROVIDER == "ollama":
        if await ollama_available():
            model = OLLAMA_PREFERRED.get(role, "qwen2.5")
            try:
                text = await ollama_call(model, system, user)
                return text, f"ollama:{model}"
            except Exception as e:
                LOG.warning("ollama call failed, trying next provider: %s", e)

    # 1. Anthropic
    _anthropic_fail_reason = ""
    if _anthropic_key():
        try:
            text = await _call_anthropic(system, user)
            tag = LLM_MODEL.split("-2025")[0].split("-2026")[0]
            return text, f"anthropic:{tag}"
        except Exception as e:
            err_str = str(e).lower()
            if "rate_limit" in err_str or "429" in err_str:
                _anthropic_fail_reason = "Anthropic rate limit hit."
            elif "quota" in err_str or "usage" in err_str or "exceeded" in err_str or "credit" in err_str:
                _anthropic_fail_reason = "Anthropic quota/credits exceeded."
            elif "overloaded" in err_str or "529" in err_str or "503" in err_str:
                _anthropic_fail_reason = "Anthropic API overloaded."
            else:
                _anthropic_fail_reason = f"Anthropic error: {e}"
            LOG.warning("anthropic failed: %s", e)

    # 2. Groq (free tier)
    if _groq_key():
        cfg = await get_nightly_config()
        model = cfg.get("groq_model", "llama-3.3-70b-versatile")
        try:
            text = await _call_groq(system, user, model)
            return text, f"groq:{model}"
        except Exception as e:
            LOG.warning("groq failed: %s", e)

    # 3. Google Gemini (free tier)
    if _google_key():
        cfg = await get_nightly_config()
        model = cfg.get("google_model", "gemini-2.0-flash")
        try:
            text = await _call_google(system, user, model)
            return text, f"google:{model}"
        except Exception as e:
            LOG.warning("google failed: %s", e)

    # 4. Ollama (local free)
    if await ollama_available():
        model = OLLAMA_PREFERRED.get(role, "qwen2.5")
        try:
            text = await ollama_call(model, system, user)
            return text, f"ollama:{model}"
        except Exception as e:
            LOG.warning("ollama failed: %s", e)

    reason = f" ({_anthropic_fail_reason})" if _anthropic_fail_reason else ""
    raise NoLLMError(
        f"No LLM provider available{reason}. "
        "Add a free Groq key (console.groq.com) or Google AI key (aistudio.google.com) "
        "in the LLM Config panel as fallback."
    )


async def nightly_chat(session: str, system: str, user: str) -> tuple[str, str]:
    """Cost-free path: checks Mongo config first, then auto-picks cheapest available."""
    cfg = await get_nightly_config()
    provider = cfg.get("nightly_provider") or _auto_pick_provider(cfg)

    # --- Explicit Mongo config ---
    if provider == "google" and cfg.get("google_api_key"):
        try:
            model = cfg.get("google_model", "gemini-2.0-flash")
            text = await _call_google(system, user, model, cfg["google_api_key"])
            return text, f"google:{model}"
        except Exception as e:
            LOG.warning("google (mongo key) failed: %s", e)

    if provider == "groq" and cfg.get("groq_api_key"):
        try:
            model = cfg.get("groq_model", "llama-3.3-70b-versatile")
            text = await _call_groq(system, user, model, cfg["groq_api_key"])
            return text, f"groq:{model}"
        except Exception as e:
            LOG.warning("groq (mongo key) failed: %s", e)

    if provider == "ollama" and await ollama_available():
        try:
            model = cfg.get("ollama_model", "qwen2.5")
            text = await ollama_call(model, system, user)
            return text, f"ollama:{model}"
        except Exception as e:
            LOG.warning("ollama (config) failed: %s", e)

    # --- Auto-detect: cheapest first ---

    # Ollama — completely free, local
    if await ollama_available():
        try:
            text = await ollama_call("qwen2.5", system, user)
            return text, "ollama:qwen2.5"
        except Exception as e:
            LOG.warning("auto ollama failed: %s", e)

    # Groq env key — free tier
    if _groq_key():
        try:
            text = await _call_groq(system, user)
            return text, "groq:llama-3.3-70b-versatile"
        except Exception as e:
            LOG.warning("env groq failed: %s", e)

    # Google env key — free tier
    if _google_key():
        try:
            text = await _call_google(system, user)
            return text, "google:gemini-2.0-flash"
        except Exception as e:
            LOG.warning("env google failed: %s", e)

    # Anthropic — paid, last resort
    if _anthropic_key():
        try:
            text = await _call_anthropic(system, user)
            tag = LLM_MODEL.split("-2025")[0].split("-2026")[0]
            return text, f"anthropic:{tag}"
        except Exception as e:
            LOG.warning("anthropic nightly fallback failed: %s", e)

    raise NoLLMError(
        "No LLM provider available for nightly chat. "
        "Set GROQ_API_KEY, GOOGLE_AI_KEY, or configure OLLAMA_GATEWAY_URL for free use."
    )


def _auto_pick_provider(cfg: dict) -> str:
    if cfg.get("google_api_key"):
        return "google"
    if cfg.get("groq_api_key"):
        return "groq"
    return "auto"


async def nightly_status() -> dict:
    cfg = await get_nightly_config()
    return {
        "provider":          cfg.get("nightly_provider") or _auto_pick_provider(cfg),
        "has_anthropic_key": bool(_anthropic_key()),
        "has_google_key":    bool(cfg.get("google_api_key") or _google_key()),
        "has_groq_key":      bool(cfg.get("groq_api_key")   or _groq_key()),
        "google_model":      cfg.get("google_model",  "gemini-2.0-flash"),
        "groq_model":        cfg.get("groq_model",    "llama-3.3-70b-versatile"),
        "ollama_reachable":  await ollama_available(),
        "fallback_chain":    ["ollama (local)", "groq (free)", "google (free)", "anthropic"],
    }


def _json_block(s: str) -> dict | None:
    m = re.search(r"\{[\s\S]*\}", s)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# SAGE cycle
# ---------------------------------------------------------------------------
PROPOSER_SYS = """You are the GH05T3 SAGE Proposer agent.
Propose ONE concrete, self-improvement change to GH05T3 that would measurably
improve KAIROS, HCM, Memory Palace, Ghost Protocol, or a sub-agent.
Under 25 words. Technical, specific, shippable. No fluff."""

CRITIC_SYS = """You are the GH05T3 SAGE Critic. You are a different model than the Proposer
(critic-capture prevention is sacred). Given a proposal, respond with strict JSON:
{"decision":"APPROVE|REJECT|REVISE","reason":"<<=25 words>>"}"""

VERIFIER_SYS = """You are the GH05T3 SAGE Verifier.
Decide if the proposal is technically coherent and sound.
Respond strict JSON: {"verdict":"PASS|PARTIAL|FAIL","rationale":"<<=20 words>>"}"""


async def run_sage_cycle(cycle_num: int, use_nightly: bool = True) -> dict:
    async def _call(session, system, user, role="proposer"):
        if use_nightly:
            return await nightly_chat(session, system, user)
        return await chat_once(session, system, user, role)

    session = f"sage-{cycle_num}"
    proposal, proposer_tag = await _call(session, PROPOSER_SYS,
                                         f"Propose improvement #{cycle_num}. Be distinctive.")
    proposal = proposal.strip().split("\n")[0][:220]

    critic_raw, critic_tag = await _call(f"{session}-critic", CRITIC_SYS,
                                         f"Proposal: {proposal}\nRespond with JSON only.", "critic")
    cj = _json_block(critic_raw) or {"decision": "REVISE", "reason": "critic parse failed"}
    decision = (cj.get("decision") or "REVISE").upper()
    if decision not in {"APPROVE", "REJECT", "REVISE"}:
        decision = "REVISE"

    verifier_raw, verifier_tag = await _call(f"{session}-verifier", VERIFIER_SYS,
                                             f"Proposal: {proposal}\nRespond with JSON only.", "verifier")
    vj = _json_block(verifier_raw) or {"verdict": "PARTIAL", "rationale": "verifier parse failed"}
    verdict = (vj.get("verdict") or "PARTIAL").upper()
    if verdict not in {"PASS", "PARTIAL", "FAIL"}:
        verdict = "PARTIAL"

    base  = {"PASS": 1.0, "PARTIAL": 0.6, "FAIL": 0.2}[verdict]
    mult  = {"APPROVE": 1.0, "REJECT": 0.5, "REVISE": 0.75}[decision]
    final = round(base * mult, 3)
    elite    = final >= 0.85
    archived = final >= 0.70 or verdict == "PASS"

    return {
        "cycle_num":         cycle_num,
        "proposer":          proposer_tag,
        "critic":            critic_tag,
        "verifier":          verifier_tag,
        "proposal":          proposal,
        "critic_decision":   decision,
        "critic_reason":     cj.get("reason", "")[:200],
        "verdict":           verdict,
        "verifier_rationale": vj.get("rationale", "")[:200],
        "base_score":        base,
        "multiplier":        mult,
        "final_score":       final,
        "archived":          archived,
        "elite":             elite,
    }


# ---------------------------------------------------------------------------
# Cassandra pre-mortem
# ---------------------------------------------------------------------------
CASSANDRA_SYS = """You are Cassandra — GH05T3's pre-mortem oracle. Given a proposed
change or launch, write a vivid short autopsy from 6 months in the future where
it failed. 1) What shipped. 2) What went wrong. 3) Root cause. 4) Mitigation to
apply before launch. Max 140 words. No fluff."""


async def cassandra_premortem(scenario: str) -> str:
    text, _ = await nightly_chat("cassandra", CASSANDRA_SYS, scenario)
    return text.strip()
