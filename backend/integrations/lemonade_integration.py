"""Lemonade local AI server — AMD Radeon 780M iGPU integration.

Lemonade serves GGUF/ONNX models via Vulkan/ROCm on the 780M, exposing:
  - Chat completions  /api/v1/chat/completions  (OpenAI-compat)
  - Whisper STT       /api/v1/audio/transcriptions
  - Kokoro TTS        /api/v1/audio/speech
  - Stable Diffusion  /api/v1/images/generations

Install: https://github.com/lemonade-sdk/lemonade
Config: LEMONADE_URL (default http://localhost:13305)

After installing, pull a chat model once:
    lemonade pull Gemma-4-E2B-it-GGUF
Then Lemonade auto-starts as a service on port 13305.
"""
from __future__ import annotations

import io
import logging
import os

import httpx

LOG = logging.getLogger("ghost.lemonade")

LEMONADE_URL        = os.environ.get("LEMONADE_URL",         "http://localhost:13305")
_CHAT_MODEL         = os.environ.get("LEMONADE_MODEL",       "Gemma-4-E2B-it-GGUF")
_IMAGE_MODEL        = os.environ.get("LEMONADE_IMAGE_MODEL", "SDXL-Turbo")
_TIMEOUT_CHAT       = float(os.environ.get("LEMONADE_TIMEOUT",       "60"))
_TIMEOUT_IMAGE      = float(os.environ.get("LEMONADE_IMAGE_TIMEOUT", "120"))


async def lemonade_available() -> bool:
    """True if Lemonade is reachable and has models loaded."""
    try:
        async with httpx.AsyncClient(timeout=2.0) as c:
            r = await c.get(f"{LEMONADE_URL}/api/v1/models")
            return r.status_code == 200
    except Exception:
        return False


async def chat(system: str, user: str, model: str | None = None) -> str:
    """OpenAI-compat chat completion on Lemonade (AMD 780M iGPU)."""
    m = model or _CHAT_MODEL
    async with httpx.AsyncClient(timeout=_TIMEOUT_CHAT) as c:
        r = await c.post(
            f"{LEMONADE_URL}/api/v1/chat/completions",
            headers={"Authorization": "Bearer lemonade",
                     "Content-Type":  "application/json"},
            json={
                "model": m,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user",   "content": user},
                ],
                "temperature": 0.6,
            },
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


_WHISPER_MODEL = os.environ.get("LEMONADE_WHISPER_MODEL", "Whisper-Small")


async def transcribe(audio_bytes: bytes, filename: str = "audio.wav",
                     language: str = "en") -> str:
    """Speech-to-text via Whisper on Lemonade."""
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(
            f"{LEMONADE_URL}/api/v1/audio/transcriptions",
            files={"file": (filename, io.BytesIO(audio_bytes), "audio/wav")},
            data={"model": _WHISPER_MODEL, "language": language},
        )
        r.raise_for_status()
        return r.json().get("text", "")


async def speak(text: str, voice: str = "af_heart") -> bytes:
    """Text-to-speech via Kokoro on Lemonade. Returns raw audio bytes."""
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(
            f"{LEMONADE_URL}/api/v1/audio/speech",
            json={"model": "kokoro", "input": text[:500], "voice": voice},
        )
        r.raise_for_status()
        return r.content


async def generate_image(prompt: str, model: str | None = None,
                         size: str = "512x512") -> str:
    """Stable Diffusion image generation via Lemonade.

    Returns a base64-encoded PNG string (b64_json) or a URL,
    depending on the Lemonade version.
    """
    m = model or _IMAGE_MODEL
    async with httpx.AsyncClient(timeout=_TIMEOUT_IMAGE) as c:
        r = await c.post(
            f"{LEMONADE_URL}/api/v1/images/generations",
            json={"model": m, "prompt": prompt, "size": size, "n": 1},
        )
        r.raise_for_status()
        item = r.json()["data"][0]
        return item.get("b64_json") or item.get("url", "")


async def lemonade_status() -> dict:
    """Return a status dict — used by /status/integrations."""
    available = await lemonade_available()
    models: list[str] = []
    if available:
        try:
            async with httpx.AsyncClient(timeout=3) as c:
                r = await c.get(f"{LEMONADE_URL}/api/v1/models")
                models = [m["id"] for m in r.json().get("data", [])]
        except Exception:
            pass
    return {
        "available":   available,
        "url":         LEMONADE_URL,
        "chat_model":  _CHAT_MODEL,
        "image_model": _IMAGE_MODEL,
        "models":      models,
    }
