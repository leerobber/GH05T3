"""LLM helpers: KAIROS SAGE cycle + Cassandra pre-mortem + free nightly router.

Chat path (expensive, personality-critical): Claude Sonnet 4.5 via Emergent key.
Nightly path (autonomy, cost-sensitive): routed per user config. In order:
    1. If Mongo `llm_config.nightly_provider` is set → honor it
    2. Else if GOOGLE_AI_KEY or GROQ_API_KEY envs exist → use them
    3. Else if OLLAMA_GATEWAY_URL reachable → use it
    4. Else fall back to Emergent key + Gemini 2.5 Flash (cheapest Universal Key option)
"""
from __future__ import annotations
import json
import os
import re
import logging
import httpx
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

from emergentintegrations.llm.chat import LlmChat, UserMessage

LOG = logging.getLogger("ghost.llm")


class BudgetExhaustedError(RuntimeError):
    """Raised when the Emergent Universal Key has run out of budget and no
    user-configured fallback provider (Google / Groq / Ollama) is available.

    Callers should surface a friendly message instructing the user to add their
    own Google AI or Groq API key via the UI settings panel.
    """


def _is_budget_exhausted(exc: Exception) -> bool:
    """Heuristic match for LiteLLM / OpenAI 'Budget has been exceeded' errors."""
    s = str(exc).lower()
    return (
        "budget has been exceeded" in s
        or "budget exceeded" in s
        or "insufficient_quota" in s
        or ("badrequesterror" in s and "budget" in s)
    )


EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY")
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "anthropic")
LLM_MODEL = os.environ.get("LLM_MODEL", "claude-sonnet-4-5-20250929")
OLLAMA_URL = os.environ.get("OLLAMA_GATEWAY_URL", "").rstrip("/")


# ---------------------------------------------------------------------------
# Nightly config (persisted in Mongo, overridable via API)
# ---------------------------------------------------------------------------
_DB_REF = {"db": None}


def bind_db(db):
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
# Providers
# ---------------------------------------------------------------------------
async def ollama_available() -> bool:
    if not OLLAMA_URL:
        return False
    try:
        async with httpx.AsyncClient(timeout=2.0) as c:
            r = await c.get(f"{OLLAMA_URL}/v1/models")
            return r.status_code == 200
    except Exception:
        return False


async def _openai_compat(base: str, api_key: str | None, model: str, system: str, user: str) -> str:
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
                    {"role": "user", "content": user},
                ],
                "temperature": 0.6,
            },
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


async def _google_ai(key: str, model: str, system: str, user: str) -> str:
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


async def _emergent(session: str, system: str, user: str,
                    provider: str = LLM_PROVIDER, model: str = LLM_MODEL) -> str:
    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY, session_id=session, system_message=system,
    ).with_model(provider, model)
    return await chat.send_message(UserMessage(text=user))


# ---------------------------------------------------------------------------
# Public chat functions
# ---------------------------------------------------------------------------
async def chat_once(session: str, system: str, user: str, role: str = "proposer") -> tuple[str, str]:
    """Default (Claude-backed, premium) chat for role-critical calls."""
    if await ollama_available():
        model = {
            "proposer": os.environ.get("OLLAMA_PROPOSER", "qwen2.5"),
            "verifier": os.environ.get("OLLAMA_VERIFIER", "deepseek-coder"),
            "critic":   os.environ.get("OLLAMA_CRITIC",   "llama3.1"),
        }.get(role, "qwen2.5")
        try:
            text = await _openai_compat(f"{OLLAMA_URL}/v1", None, model, system, user)
            return text, f"ollama:{model}"
        except Exception as e:  # noqa: BLE001
            LOG.warning("ollama call failed, falling back: %s", e)
    text = await _emergent(session, system, user)
    return text, f"{LLM_PROVIDER}:{LLM_MODEL.split('-2025')[0]}"


async def nightly_chat(session: str, system: str, user: str) -> tuple[str, str]:
    """Free/cheap model for nightly autonomy. Picks best available provider."""
    cfg = await get_nightly_config()
    provider = cfg.get("nightly_provider") or _auto_pick_provider(cfg)

    # 1. Explicit user config
    if provider == "google" and cfg.get("google_api_key"):
        try:
            text = await _google_ai(
                cfg["google_api_key"],
                cfg.get("google_model", "gemini-2.5-flash"),
                system, user,
            )
            return text, f"google:{cfg.get('google_model', 'gemini-2.5-flash')}"
        except Exception as e:  # noqa: BLE001
            LOG.warning("google free call failed: %s", e)

    if provider == "groq" and cfg.get("groq_api_key"):
        try:
            text = await _openai_compat(
                "https://api.groq.com/openai/v1",
                cfg["groq_api_key"],
                cfg.get("groq_model", "llama-3.3-70b-versatile"),
                system, user,
            )
            return text, f"groq:{cfg.get('groq_model', 'llama-3.3-70b-versatile')}"
        except Exception as e:  # noqa: BLE001
            LOG.warning("groq call failed: %s", e)

    if provider == "ollama" and await ollama_available():
        try:
            model = cfg.get("ollama_model", "qwen2.5")
            text = await _openai_compat(f"{OLLAMA_URL}/v1", None, model, system, user)
            return text, f"ollama:{model}"
        except Exception as e:  # noqa: BLE001
            LOG.warning("ollama call failed: %s", e)

    # 2. Auto-detect env-provided keys (no Mongo config needed)
    gkey = os.environ.get("GOOGLE_AI_KEY")
    if gkey:
        try:
            text = await _google_ai(gkey, "gemini-2.5-flash", system, user)
            return text, "google:gemini-2.5-flash"
        except Exception as e:  # noqa: BLE001
            LOG.warning("env google call failed: %s", e)

    grkey = os.environ.get("GROQ_API_KEY")
    if grkey:
        try:
            text = await _openai_compat(
                "https://api.groq.com/openai/v1", grkey,
                "llama-3.3-70b-versatile", system, user,
            )
            return text, "groq:llama-3.3-70b"
        except Exception as e:  # noqa: BLE001
            LOG.warning("env groq call failed: %s", e)

    if await ollama_available():
        try:
            text = await _openai_compat(f"{OLLAMA_URL}/v1", None, "qwen2.5", system, user)
            return text, "ollama:qwen2.5"
        except Exception as e:  # noqa: BLE001
            LOG.warning("auto ollama call failed: %s", e)

    # 3. Absolute fallback → Emergent + cheapest model
    try:
        text = await _emergent(session, system, user, "gemini", "gemini-2.5-flash")
        return text, "emergent:gemini-2.5-flash"
    except Exception as e:  # noqa: BLE001
        if _is_budget_exhausted(e):
            LOG.error("emergent gemini fallback: budget exhausted")
            raise BudgetExhaustedError(
                "Emergent Universal Key budget exhausted and no user "
                "Google/Groq key configured."
            ) from e
        LOG.warning("emergent gemini fallback failed: %s, trying claude-haiku", e)
        try:
            text = await _emergent(session, system, user, "anthropic", "claude-haiku-4-5-20251001")
            return text, "emergent:claude-haiku"
        except Exception as e2:  # noqa: BLE001
            if _is_budget_exhausted(e2):
                LOG.error("emergent claude-haiku fallback: budget exhausted")
                raise BudgetExhaustedError(
                    "Emergent Universal Key budget exhausted and no user "
                    "Google/Groq key configured."
                ) from e2
            raise


def _auto_pick_provider(cfg: dict) -> str:
    if cfg.get("google_api_key"):
        return "google"
    if cfg.get("groq_api_key"):
        return "groq"
    return "auto"


async def nightly_status() -> dict:
    cfg = await get_nightly_config()
    return {
        "provider": cfg.get("nightly_provider") or _auto_pick_provider(cfg),
        "has_google_key": bool(cfg.get("google_api_key") or os.environ.get("GOOGLE_AI_KEY")),
        "has_groq_key": bool(cfg.get("groq_api_key") or os.environ.get("GROQ_API_KEY")),
        "google_model": cfg.get("google_model", "gemini-2.5-flash"),
        "groq_model": cfg.get("groq_model", "llama-3.3-70b-versatile"),
        "ollama_reachable": await ollama_available(),
        "fallback": "emergent:gemini-2.5-flash",
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
# SAGE cycle (now uses nightly_chat by default — free)
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
    """Run a full SAGE cycle. use_nightly=True (default) uses the free/cheap router."""

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

    base = {"PASS": 1.0, "PARTIAL": 0.6, "FAIL": 0.2}[verdict]
    mult = {"APPROVE": 1.0, "REJECT": 0.5, "REVISE": 0.75}[decision]
    final = round(base * mult, 3)
    elite = final >= 0.85
    archived = final >= 0.70 or verdict == "PASS"

    return {
        "cycle_num": cycle_num,
        "proposer": proposer_tag, "critic": critic_tag, "verifier": verifier_tag,
        "proposal": proposal, "critic_decision": decision,
        "critic_reason": cj.get("reason", "")[:200],
        "verdict": verdict,
        "verifier_rationale": vj.get("rationale", "")[:200],
        "base_score": base, "multiplier": mult, "final_score": final,
        "archived": archived, "elite": elite,
    }


# ---------------------------------------------------------------------------
# Cassandra pre-mortem
# ---------------------------------------------------------------------------
CASSANDRA_SYS = """You are Cassandra — GH05T3's pre-mortem oracle. Given a proposed
change or launch, write a vivid short autopsy from 6 months in the future where
it failed. 1) What shipped. 2) What went wrong. 3) Root cause. 4) Mitigation to
apply before launch. Max 140 words. No fluff."""


async def cassandra_premortem(scenario: str) -> str:
    # Cassandra is also free/cheap — use nightly router
    text, _ = await nightly_chat("cassandra", CASSANDRA_SYS, scenario)
    return text.strip()
