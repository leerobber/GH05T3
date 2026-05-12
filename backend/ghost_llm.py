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

LLM_PROVIDER    = os.environ.get("LLM_PROVIDER",    "ollama")
LLM_MODEL       = os.environ.get("LLM_MODEL",       "claude-sonnet-4-6")
ANTHROPIC_MODEL = os.environ.get("LLM_MODEL",       "claude-sonnet-4-6")

# GH05T3 fine-tuned model — served by gh05t3_inference.py on port 8010
GH05T3_MODEL_URL = os.environ.get("GH05T3_MODEL_URL", "http://localhost:8010")

_LOCAL_ONLY_PROVIDERS = {"ollama", "local", "free", "cost_free", "cost-free", "gh05t3"}
_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}


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
    key = _env_key("ANTHROPIC_API_KEY")
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
    key = api_key or _env_key("GROQ_API_KEY")
    if not key:
        raise RuntimeError("GROQ_API_KEY not set")
    return await _openai_compat(
        "https://api.groq.com/openai/v1", key, model, system, user,
    )


async def _call_google(system: str, user: str,
                       model: str = "gemini-2.0-flash",
                       api_key: str | None = None) -> str:
    key = api_key or _env_key("GOOGLE_AI_KEY")
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
# GH05T3 fine-tuned model
# ---------------------------------------------------------------------------
async def gh05t3_available() -> bool:
    """Return True if the local GH05T3 inference server is running."""
    if not GH05T3_MODEL_URL:
        return False
    try:
        async with httpx.AsyncClient(timeout=2.0) as c:
            r = await c.get(f"{GH05T3_MODEL_URL}/health")
            return r.status_code == 200 and r.json().get("status") == "ready"
    except Exception:
        return False


async def _call_gh05t3(system: str, user: str) -> str:
    return await _openai_compat(
        base    = GH05T3_MODEL_URL,
        api_key = None,
        model   = "gh05t3",
        system  = system,
        user    = user,
    )


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


async def ollama_ensure_model(model: str = "qwen2.5:0.5b") -> bool:
    """Pull a small Ollama model if Ollama is running but has no models loaded.
    qwen2.5:0.5b is ~400 MB — guaranteed local fallback."""
    url = ollama_resolved_url()
    if not url:
        return False
    try:
        async with httpx.AsyncClient(timeout=5.0) as c:
            r = await c.get(f"{url}/api/tags")
            if r.status_code != 200:
                return False
            models = [m["name"] for m in r.json().get("models", [])]
            if models:
                return True  # already has models
            # Pull the smallest useful model
            LOG.info("[ollama] no models found, pulling %s as fallback...", model)
            pull = await c.post(f"{url}/api/pull", json={"name": model}, timeout=600)
            return pull.status_code == 200
    except Exception as e:
        LOG.warning("[ollama] ensure_model failed: %s", e)
        return False


_ENV_PATH = Path(__file__).parent / ".env"


def _classify_anthropic_error(e: Exception) -> str:
    """Return a short human-readable reason for an Anthropic failure."""
    s = str(e).lower()
    if "rate_limit" in s or "429" in s:
        return "Anthropic rate limit hit"
    if any(w in s for w in ("quota", "usage", "exceeded", "credit", "budget")):
        return "Anthropic quota/budget exceeded"
    if "overloaded" in s or "529" in s or "503" in s:
        return "Anthropic API overloaded"
    if "401" in s or "authentication" in s or "invalid.*key" in s:
        return "Anthropic API key invalid"
    return f"Anthropic error: {type(e).__name__}"


def _env_key(name: str) -> str:
    """Read key from os.environ, then re-read .env file so hot-saved keys (written by
    the gateway process after server startup) are always picked up without a restart."""
    val = os.environ.get(name, "")
    if val:
        return val
    try:
        from dotenv import dotenv_values
        val = dotenv_values(_ENV_PATH).get(name, "") or ""
        if val:
            os.environ[name] = val  # cache into env so next call is fast
    except Exception:
        pass
    return val


def _anthropic_key() -> str:
    return _env_key("ANTHROPIC_API_KEY")


def _groq_key() -> str:
    return _env_key("GROQ_API_KEY")


def _google_key() -> str:
    return _env_key("GOOGLE_AI_KEY")


def _llm_provider() -> str:
    return (os.environ.get("LLM_PROVIDER") or LLM_PROVIDER or "ollama").strip().lower()


def _cost_free_only() -> bool:
    raw = os.environ.get("COST_FREE_ONLY")
    if raw is not None:
        return raw.strip().lower() not in _FALSE_VALUES
    return _llm_provider() in _LOCAL_ONLY_PROVIDERS


def _paid_llm_allowed() -> bool:
    return os.environ.get("ALLOW_PAID_LLM", "").strip().lower() in _TRUE_VALUES


async def _call_ollama_preferred(system: str, user: str, role: str = "proposer") -> tuple[str, str]:
    if not await ollama_available():
        raise RuntimeError("Ollama is not reachable at OLLAMA_GATEWAY_URL")
    await ollama_ensure_model("qwen2.5:0.5b")
    model = OLLAMA_PREFERRED.get(role) or OLLAMA_PREFERRED.get("proposer") or "qwen2.5:0.5b"
    text = await ollama_call(model, system, user)
    return text, f"ollama:{model}"


# ---------------------------------------------------------------------------
# Public chat functions
# ---------------------------------------------------------------------------
async def chat_once(session: str, system: str, user: str,
                    role: str = "proposer") -> tuple[str, str]:
    """Main chat path.

    Defaults to local Ollama only. Cloud providers require COST_FREE_ONLY=0,
    and paid Anthropic additionally requires ALLOW_PAID_LLM=1.
    """
    provider = _llm_provider()

    # 0. GH05T3 fine-tuned model — highest priority when running locally
    if provider == "gh05t3" or (provider in {"auto"} and await gh05t3_available()):
        try:
            text = await _call_gh05t3(system, user)
            return text, "gh05t3:local"
        except Exception as e:
            LOG.warning("gh05t3 local inference failed: %s", e)
            if provider == "gh05t3":
                raise NoLLMError(
                    f"GH05T3 inference server unavailable at {GH05T3_MODEL_URL}. "
                    "Run: python gh05t3_inference.py"
                ) from e

    if _cost_free_only() or provider in _LOCAL_ONLY_PROVIDERS:
        try:
            return await _call_ollama_preferred(system, user, role)
        except Exception as e:
            LOG.warning("ollama local-only chat failed: %s", e)
            raise NoLLMError(
                "Local free LLM unavailable. Start Ollama and verify "
                "OLLAMA_GATEWAY_URL, or explicitly disable COST_FREE_ONLY to use cloud providers."
            ) from e

    # 1. Anthropic, paid and explicit opt-in only
    _fail_reason = ""
    if provider == "anthropic" and _paid_llm_allowed() and _anthropic_key():
        try:
            text = await _call_anthropic(system, user)
            tag = LLM_MODEL.split("-2025")[0].split("-2026")[0]
            return text, f"anthropic:{tag}"
        except Exception as e:
            _fail_reason = _classify_anthropic_error(e)
            LOG.warning("anthropic failed (%s): %s", _fail_reason, e)

    # 2. Groq (free tier) — env/file first, then MongoDB config as fallback
    cfg = await get_nightly_config()
    groq_key = _groq_key() or cfg.get("groq_api_key", "")
    if provider in {"auto", "groq"} and groq_key:
        model = cfg.get("groq_model", "llama-3.3-70b-versatile")
        try:
            text = await _call_groq(system, user, model, api_key=groq_key)
            return text, f"groq:{model}"
        except Exception as e:
            LOG.warning("groq failed: %s", e)

    # 3. Google Gemini (free tier) — env/file first, then MongoDB config as fallback
    google_key = _google_key() or cfg.get("google_api_key", "")
    if provider in {"auto", "google"} and google_key:
        model = cfg.get("google_model", "gemini-2.0-flash")
        try:
            text = await _call_google(system, user, model, api_key=google_key)
            return text, f"google:{model}"
        except Exception as e:
            LOG.warning("google failed: %s", e)

    # 4. Ollama (local free) — silent fallback; auto-pull tiny model if needed
    try:
        return await _call_ollama_preferred(system, user, role)
    except Exception as e:
        LOG.warning("ollama failed: %s", e)

    # All providers exhausted — only NOW tell the user
    reason = f" ({_fail_reason})" if _fail_reason else ""
    raise NoLLMError(
        f"No LLM provider available{reason}. "
        "Add a free Groq key (console.groq.com) or Google AI key (aistudio.google.com) "
        "in the LLM Config panel as fallback."
    )


async def nightly_chat(session: str, system: str, user: str) -> tuple[str, str]:
    """Cost-free path: checks Mongo config first, then auto-picks cheapest available."""
    if _cost_free_only():
        try:
            return await _call_ollama_preferred(system, user, "proposer")
        except Exception as e:
            LOG.warning("ollama local-only nightly failed: %s", e)
            raise NoLLMError(
                "Local free LLM unavailable for nightly/background work. Start Ollama "
                "and verify OLLAMA_GATEWAY_URL."
            ) from e

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

    # Ollama — completely free, local; auto-pull tiny model if needed
    if await ollama_available():
        await ollama_ensure_model("qwen2.5:0.5b")
        try:
            text = await ollama_call("qwen2.5", system, user)
            return text, "ollama:qwen2.5"
        except Exception as e:
            LOG.warning("auto ollama failed: %s", e)

    # Groq env key — free tier (pass key explicitly so hot-reload works)
    groq_key = _groq_key()
    if groq_key:
        try:
            text = await _call_groq(system, user, api_key=groq_key)
            return text, "groq:llama-3.3-70b-versatile"
        except Exception as e:
            LOG.warning("env groq failed: %s", e)

    # Google env key — free tier
    google_key = _google_key()
    if google_key:
        try:
            text = await _call_google(system, user, api_key=google_key)
            return text, "google:gemini-2.0-flash"
        except Exception as e:
            LOG.warning("env google failed: %s", e)

    # Anthropic — paid, last resort for nightly and explicit opt-in only
    _fail_reason = ""
    if _paid_llm_allowed() and _anthropic_key():
        try:
            text = await _call_anthropic(system, user)
            tag = LLM_MODEL.split("-2025")[0].split("-2026")[0]
            return text, f"anthropic:{tag}"
        except Exception as e:
            _fail_reason = _classify_anthropic_error(e)
            LOG.warning("anthropic nightly failed (%s): %s", _fail_reason, e)

    reason = f" ({_fail_reason})" if _fail_reason else ""
    raise NoLLMError(
        f"No LLM provider available for nightly chat{reason}. "
        "Set GROQ_API_KEY or GOOGLE_AI_KEY in the LLM Config panel for free fallback."
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
