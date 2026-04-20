"""LLM helpers: KAIROS SAGE cycle + Cassandra pre-mortem.
Uses emergentintegrations (Claude Sonnet 4.5). Falls back to an Ollama
OpenAI-compatible gateway if OLLAMA_GATEWAY_URL is set and reachable.
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

EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY")
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "anthropic")
LLM_MODEL = os.environ.get("LLM_MODEL", "claude-sonnet-4-5-20250929")
OLLAMA_URL = os.environ.get("OLLAMA_GATEWAY_URL", "").rstrip("/")


async def ollama_available() -> bool:
    if not OLLAMA_URL:
        return False
    try:
        async with httpx.AsyncClient(timeout=2.0) as c:
            r = await c.get(f"{OLLAMA_URL}/v1/models")
            return r.status_code == 200
    except Exception:
        return False


async def _ollama_chat(model: str, system: str, user: str) -> str:
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(
            f"{OLLAMA_URL}/v1/chat/completions",
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


async def _emergent_chat(session: str, system: str, user: str, model: str | None = None) -> str:
    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY, session_id=session, system_message=system
    ).with_model(LLM_PROVIDER, model or LLM_MODEL)
    return await chat.send_message(UserMessage(text=user))


async def chat_once(session: str, system: str, user: str, role: str = "proposer") -> tuple[str, str]:
    """Returns (text, engine_tag). engine_tag e.g. 'claude-sonnet-4-5' or 'ollama:qwen2.5'."""
    if await ollama_available():
        model = {
            "proposer": os.environ.get("OLLAMA_PROPOSER", "qwen2.5"),
            "verifier": os.environ.get("OLLAMA_VERIFIER", "deepseek-coder"),
            "critic":   os.environ.get("OLLAMA_CRITIC",   "llama3.1"),
        }.get(role, "qwen2.5")
        try:
            text = await _ollama_chat(model, system, user)
            return text, f"ollama:{model}"
        except Exception as e:  # noqa: BLE001
            LOG.warning("ollama call failed, falling back: %s", e)
    text = await _emergent_chat(session, system, user)
    return text, f"{LLM_PROVIDER}:{LLM_MODEL.split('-2025')[0]}"


def _json_block(s: str) -> dict | None:
    m = re.search(r"\{[\s\S]*\}", s)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# SAGE 4-agent cycle: Proposer -> Critic -> Verifier -> Meta
# ---------------------------------------------------------------------------
PROPOSER_SYS = """You are the GH05T3 SAGE Proposer agent running on RTX 5050 (Qwen2.5).
Your job: propose ONE concrete, self-improvement change to GH05T3 that would
measurably improve KAIROS, HCM, Memory Palace, Ghost Protocol, or a sub-agent.
Keep it under 25 words. Technical, specific, shippable. No fluff."""

CRITIC_SYS = """You are the GH05T3 SAGE Critic. You are a different model than the Proposer
(critic-capture prevention is sacred). Given a proposal, respond with strict JSON:
{"decision":"APPROVE|REJECT|REVISE","reason":"<<=25 words>>"}"""

VERIFIER_SYS = """You are the GH05T3 SAGE Verifier running on Radeon 780M (DeepSeek-Coder).
Decide if the proposal is technically coherent and mathematically/architecturally sound.
Respond with strict JSON: {"verdict":"PASS|PARTIAL|FAIL","rationale":"<<=20 words>>"}"""


async def run_sage_cycle(cycle_num: int) -> dict:
    session = f"sage-{cycle_num}"
    proposal, proposer_tag = await chat_once(
        session, PROPOSER_SYS,
        f"Propose improvement #{cycle_num}. Be distinctive.", "proposer",
    )
    proposal = proposal.strip().split("\n")[0][:220]

    critic_raw, critic_tag = await chat_once(
        f"{session}-critic", CRITIC_SYS,
        f"Proposal: {proposal}\nRespond with JSON only.", "critic",
    )
    cj = _json_block(critic_raw) or {"decision": "REVISE", "reason": "critic parse failed"}
    decision = (cj.get("decision") or "REVISE").upper()
    if decision not in {"APPROVE", "REJECT", "REVISE"}:
        decision = "REVISE"

    verifier_raw, verifier_tag = await chat_once(
        f"{session}-verifier", VERIFIER_SYS,
        f"Proposal: {proposal}\nRespond with JSON only.", "verifier",
    )
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
        "proposer": proposer_tag,
        "critic": critic_tag,
        "verifier": verifier_tag,
        "proposal": proposal,
        "critic_decision": decision,
        "critic_reason": cj.get("reason", "")[:200],
        "verdict": verdict,
        "verifier_rationale": vj.get("rationale", "")[:200],
        "base_score": base,
        "multiplier": mult,
        "final_score": final,
        "archived": archived,
        "elite": elite,
    }


# ---------------------------------------------------------------------------
# Cassandra pre-mortem
# ---------------------------------------------------------------------------
CASSANDRA_SYS = """You are Cassandra — GH05T3's pre-mortem oracle. Given a proposed
change or launch, you write a vivid short autopsy from 6 months in the future
where it failed. Structure: 1) What shipped. 2) What went wrong. 3) Root cause.
4) Mitigation to apply before launch. Max 140 words, no fluff."""


async def cassandra_premortem(scenario: str) -> str:
    text, _ = await chat_once("cassandra", CASSANDRA_SYS, scenario, "critic")
    return text.strip()
