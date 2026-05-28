import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import ghost_llm  # noqa: E402


@pytest.mark.anyio
async def test_chat_once_ollama_mode_never_calls_external_providers(monkeypatch):
    called = []

    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("COST_FREE_ONLY", "1")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "present")
    monkeypatch.setenv("GROQ_API_KEY", "present")
    monkeypatch.setenv("GOOGLE_AI_KEY", "present")
    monkeypatch.setattr(ghost_llm, "LLM_PROVIDER", "ollama")
    monkeypatch.setattr(ghost_llm, "_anthropic_key", lambda: "present")
    monkeypatch.setattr(ghost_llm, "_groq_key", lambda: "present")
    monkeypatch.setattr(ghost_llm, "_google_key", lambda: "present")
    async def empty_config():
        return {}

    async def unavailable():
        return False

    monkeypatch.setattr(ghost_llm, "get_nightly_config", empty_config)
    monkeypatch.setattr(ghost_llm, "ollama_available", unavailable)

    async def external(*args, **kwargs):
        called.append("external")
        return "paid"

    monkeypatch.setattr(ghost_llm, "_call_anthropic", external)
    monkeypatch.setattr(ghost_llm, "_call_groq", external)
    monkeypatch.setattr(ghost_llm, "_call_google", external)

    with pytest.raises(ghost_llm.NoLLMError):
        await ghost_llm.chat_once("s", "system", "user")

    assert called == []


@pytest.mark.anyio
async def test_nightly_chat_cost_free_never_calls_external_providers(monkeypatch):
    called = []

    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("COST_FREE_ONLY", "1")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "present")
    monkeypatch.setenv("GROQ_API_KEY", "present")
    monkeypatch.setenv("GOOGLE_AI_KEY", "present")
    monkeypatch.setattr(ghost_llm, "LLM_PROVIDER", "ollama")
    async def empty_config():
        return {}

    async def unavailable():
        return False

    monkeypatch.setattr(ghost_llm, "get_nightly_config", empty_config)
    monkeypatch.setattr(ghost_llm, "ollama_available", unavailable)

    async def external(*args, **kwargs):
        called.append("external")
        return "cloud"

    monkeypatch.setattr(ghost_llm, "_call_anthropic", external)
    monkeypatch.setattr(ghost_llm, "_call_groq", external)
    monkeypatch.setattr(ghost_llm, "_call_google", external)

    with pytest.raises(ghost_llm.NoLLMError):
        await ghost_llm.nightly_chat("s", "system", "user")

    assert called == []
