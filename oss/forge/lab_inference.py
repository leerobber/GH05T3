"""Lab inference — route Builder/Investor roles through domain_research_adapter."""
from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any

LOG = logging.getLogger("oss.forge.lab_inference")

_REPO = Path(__file__).resolve().parents[2]
_DEFAULT_ADAPTER = _REPO / "backend" / "models" / "domain_research_adapter"
_INFERENCE_URL = os.environ.get("GH05T3_INFERENCE_URL", "http://127.0.0.1:8010")


def adapter_on_disk(bucket: str = "business") -> bool:
    from oss.forge.moe_farm import adapter_dir_for_bucket
    path = _REPO / "backend" / "models" / adapter_dir_for_bucket(bucket)
    return (path / "adapter_config.json").exists()


def inference_server_ready() -> bool:
    try:
        import httpx
        r = httpx.get(f"{_INFERENCE_URL}/health", timeout=2.0)
        if r.status_code != 200:
            return False
        data = r.json()
        return data.get("status") == "ready"
    except Exception:
        return False


def _parse_json_blob(text: str) -> dict[str, Any] | None:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            return None
    return None


def complete_with_adapter(
    *,
    prompt: str,
    system: str = "",
    traits: dict[str, float] | None = None,
    role: str = "builder",
    bucket: str = "business",
    temperature: float = 0.55,
    max_tokens: int = 512,
    timeout: float = 45.0,
) -> dict[str, Any]:
    """
    Call gh05t3_inference with task_domain=business (domain_research_adapter).

    Returns {"text", "source", "adapter_bucket", "parsed"}.
    Falls back to None text when server unavailable — caller uses heuristics.
    """
    trait_block = ""
    if traits:
        trait_block = "Traits: " + ", ".join(f"{k}={v:.2f}" for k, v in traits.items())

    messages = []
    sys_content = (
        f"You are a {role} agent designing SaaS products. {trait_block}\n"
        "Respond with compact JSON: name, target_segment, value_prop, features (list), "
        "pricing (object with tier and price).\n"
    )
    if system:
        sys_content += system + "\n"
    messages.append({"role": "system", "content": sys_content})
    messages.append({"role": "user", "content": prompt})

    if not inference_server_ready():
        return {
            "text": "",
            "source": "unavailable",
            "adapter_bucket": bucket,
            "parsed": None,
            "reason": "inference_server_not_ready",
        }

    try:
        import httpx
        payload = {
            "model": "gh05t3",
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
            "task_domain": bucket,
            "session_id": f"lab_{role}",
        }
        r = httpx.post(
            f"{_INFERENCE_URL}/v1/chat/completions",
            json=payload,
            timeout=timeout,
        )
        r.raise_for_status()
        body = r.json()
        text = body["choices"][0]["message"]["content"]
        route_meta = body.get("route") or {}
        return {
            "text": text,
            "source": "domain_research_adapter",
            "adapter_bucket": route_meta.get("adapter_bucket", bucket),
            "parsed": _parse_json_blob(text),
            "route": route_meta,
        }
    except Exception as exc:
        LOG.warning("lab inference failed: %s", exc)
        return {
            "text": "",
            "source": "error",
            "adapter_bucket": bucket,
            "parsed": None,
            "reason": str(exc),
        }


def lab_inference_status() -> dict[str, Any]:
    return {
        "adapter_path": str(_DEFAULT_ADAPTER),
        "adapter_on_disk": adapter_on_disk("business"),
        "inference_url": _INFERENCE_URL,
        "inference_ready": inference_server_ready(),
        "bucket": "business",
        "roles": ["builder", "investor"],
    }