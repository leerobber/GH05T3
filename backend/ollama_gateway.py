"""Ollama gateway helpers for GH05T3 on LOQ (TatorTot).

Resolves `OLLAMA_GATEWAY_URL` from env/Mongo config, exposes health +
model list, and surfaces the models GH05T3 prefers:
    - Proposer / chat:  qwen2.5:7b-q4
    - Verifier / coder: deepseek-coder:6.7b
    - Critic:           llama3.1
"""
from __future__ import annotations

import os
import re
import logging

import httpx

LOG = logging.getLogger("ghost.ollama")

PREFERRED = {
    "proposer": os.environ.get("OLLAMA_PROPOSER", "qwen2.5:7b-q4"),
    "verifier": os.environ.get("OLLAMA_VERIFIER", "deepseek-coder:6.7b"),
    "critic": os.environ.get("OLLAMA_CRITIC", "llama3.1"),
}


def resolved_url() -> str:
    return (os.environ.get("OLLAMA_GATEWAY_URL") or "").rstrip("/")


async def ping() -> dict:
    url = resolved_url()
    if not url:
        return {"reachable": False, "url": None, "models": [], "preferred": PREFERRED,
                "error": "OLLAMA_GATEWAY_URL not set"}
    try:
        async with httpx.AsyncClient(timeout=3.0) as c:
            r = await c.get(f"{url}/v1/models")
            r.raise_for_status()
            j = r.json()
            models = [m.get("id") for m in j.get("data", []) if m.get("id")]
            return {
                "reachable": True, "url": url, "models": models,
                "preferred": PREFERRED,
                "has_proposer": any(PREFERRED["proposer"] in m for m in models),
                "has_verifier": any(PREFERRED["verifier"] in m for m in models),
            }
    except Exception as e:  # noqa: BLE001
        return {"reachable": False, "url": url, "models": [], "preferred": PREFERRED,
                "error": str(e)[:140]}


async def pull_model(model: str) -> dict:
    """Trigger a pull on the remote Ollama (non-blocking; returns immediately)."""
    url = resolved_url()
    if not url:
        return {"ok": False, "error": "OLLAMA_GATEWAY_URL not set"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as c:
            # Ollama's native pull endpoint is /api/pull (stream: false for sync)
            r = await c.post(f"{url}/api/pull", json={"name": model, "stream": False})
            r.raise_for_status()
            return {"ok": True, "model": model, "status": r.json().get("status", "ok")}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "model": model, "error": str(e)[:200]}


async def set_gateway_url(db, url: str) -> dict:
    """Persist gateway URL in Mongo + live env so reloads keep it.
    Validates URL shape before persistence."""
    url = (url or "").strip().rstrip("/")
    if url and not re.match(r"^https?://[\w\.\-]+(:\d+)?(/.*)?$", url):
        return {"reachable": False, "url": None, "error": "invalid url shape",
                "models": [], "preferred": PREFERRED}
    os.environ["OLLAMA_GATEWAY_URL"] = url
    await db.llm_config.update_one(
        {"_id": "ollama"}, {"$set": {"gateway_url": url}}, upsert=True,
    )
    return await ping()


async def load_gateway_url(db) -> str:
    """Call at startup to hydrate env from Mongo if set."""
    doc = await db.llm_config.find_one({"_id": "ollama"}, {"_id": 0})
    if doc and doc.get("gateway_url"):
        os.environ["OLLAMA_GATEWAY_URL"] = doc["gateway_url"]
        LOG.info("ollama: gateway url loaded from mongo: %s", doc["gateway_url"])
        return doc["gateway_url"]
    return ""
