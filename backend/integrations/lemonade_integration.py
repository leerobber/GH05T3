"""Lemonade local AI server — AMD Radeon 780M iGPU + CPU-native STT/TTS.

VRAM strategy — 780M stays on chat full-time:
  Chat       → Lemonade/780M (Gemma, always resident)            ~2 GB VRAM
  STT        → faster-whisper on CPU  (pip install faster-whisper)   0 VRAM
  TTS        → kokoro on CPU          (pip install kokoro soundfile)  0 VRAM
  Image gen  → Lemonade/780M SD (model swap on demand)           ~4 GB VRAM

If the CPU packages aren't installed, STT and TTS gracefully fall back
to Lemonade (which causes a model swap but still works).

Config env vars:
  LEMONADE_URL              default http://localhost:13305
  LEMONADE_MODEL            default Gemma-4-E2B-it-GGUF
  LEMONADE_IMAGE_MODEL      default SDXL-Turbo
  LEMONADE_WHISPER_MODEL    default Whisper-Small  (Lemonade fallback only)
  WHISPER_CPU_MODEL         default small          (faster-whisper size)
  LEMONADE_TIMEOUT          default 60s
  LEMONADE_IMAGE_TIMEOUT    default 120s
"""
from __future__ import annotations

import asyncio
import io
import logging
import os
import tempfile
import wave

import httpx

LOG = logging.getLogger("ghost.lemonade")

LEMONADE_URL     = os.environ.get("LEMONADE_URL",          "http://localhost:13305")
_CHAT_MODEL      = os.environ.get("LEMONADE_MODEL",        "Gemma-4-E2B-it-GGUF")
_IMAGE_MODEL     = os.environ.get("LEMONADE_IMAGE_MODEL",  "SDXL-Turbo")
_WHISPER_MODEL   = os.environ.get("LEMONADE_WHISPER_MODEL","Whisper-Small")
_WHISPER_CPU_SZ  = os.environ.get("WHISPER_CPU_MODEL",     "small")
_TIMEOUT_CHAT    = float(os.environ.get("LEMONADE_TIMEOUT",       "60"))
_TIMEOUT_IMAGE   = float(os.environ.get("LEMONADE_IMAGE_TIMEOUT", "120"))

# ---------------------------------------------------------------------------
# Lazy-loaded CPU model handles (loaded once, reused forever)
# ---------------------------------------------------------------------------
_cpu_whisper = None   # faster-whisper WhisperModel
_cpu_kokoro  = None   # kokoro KPipeline


def _get_whisper():
    global _cpu_whisper
    if _cpu_whisper is None:
        from faster_whisper import WhisperModel
        LOG.info("[lemonade] loading faster-whisper/%s on CPU", _WHISPER_CPU_SZ)
        _cpu_whisper = WhisperModel(_WHISPER_CPU_SZ, device="cpu", compute_type="int8")
    return _cpu_whisper


def _get_kokoro():
    global _cpu_kokoro
    if _cpu_kokoro is None:
        from kokoro import KPipeline
        LOG.info("[lemonade] loading kokoro TTS pipeline on CPU")
        _cpu_kokoro = KPipeline(lang_code="a")   # 'a' = American English
    return _cpu_kokoro


# ---------------------------------------------------------------------------
# Lemonade availability
# ---------------------------------------------------------------------------

async def lemonade_available() -> bool:
    """True if Lemonade server is reachable on port 13305."""
    try:
        async with httpx.AsyncClient(timeout=2.0) as c:
            r = await c.get(f"{LEMONADE_URL}/api/v1/models")
            return r.status_code == 200
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Chat — always goes to Lemonade/780M
# ---------------------------------------------------------------------------

async def chat(system: str, user: str, model: str | None = None) -> str:
    """OpenAI-compat chat via Lemonade (AMD Radeon 780M iGPU)."""
    m = model or _CHAT_MODEL
    async with httpx.AsyncClient(timeout=_TIMEOUT_CHAT) as c:
        r = await c.post(
            f"{LEMONADE_URL}/api/v1/chat/completions",
            headers={"Authorization": "Bearer lemonade",
                     "Content-Type":  "application/json"},
            json={
                "model": m,
                "messages": [{"role": "system", "content": system},
                             {"role": "user",   "content": user}],
                "temperature": 0.6,
            },
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


# ---------------------------------------------------------------------------
# STT — CPU-first (faster-whisper), Lemonade fallback
# ---------------------------------------------------------------------------

def _transcribe_cpu(audio_bytes: bytes, language: str) -> str:
    """Blocking transcription via faster-whisper on CPU."""
    model = _get_whisper()
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(audio_bytes)
        tmp = f.name
    try:
        segments, _ = model.transcribe(tmp, language=language, beam_size=1)
        return " ".join(s.text for s in segments).strip()
    finally:
        os.unlink(tmp)


async def transcribe(audio_bytes: bytes, filename: str = "audio.wav",
                     language: str = "en") -> str:
    """Speech-to-text.

    Primary: faster-whisper on CPU — zero VRAM, 780M stays on chat model.
    Fallback: Lemonade Whisper (causes model swap on 780M).
    """
    try:
        return await asyncio.to_thread(_transcribe_cpu, audio_bytes, language)
    except ImportError:
        LOG.debug("[lemonade] faster-whisper not installed — falling back to Lemonade STT")
    except Exception as e:
        LOG.warning("[lemonade] CPU transcribe failed: %s — falling back to Lemonade STT", e)

    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(
            f"{LEMONADE_URL}/api/v1/audio/transcriptions",
            files={"file": (filename, io.BytesIO(audio_bytes), "audio/wav")},
            data={"model": _WHISPER_MODEL, "language": language},
        )
        r.raise_for_status()
        return r.json().get("text", "")


# ---------------------------------------------------------------------------
# TTS — CPU-first (kokoro), Lemonade fallback
# ---------------------------------------------------------------------------

def _speak_cpu(text: str, voice: str) -> bytes:
    """Blocking TTS via kokoro on CPU. Returns WAV bytes."""
    import numpy as np
    pipeline = _get_kokoro()
    audio_chunks = []
    sample_rate  = 24000   # kokoro native output rate
    for _, _, audio in pipeline(text[:500], voice=voice, speed=1.0):
        audio_chunks.append(audio)

    if not audio_chunks:
        raise RuntimeError("kokoro produced no audio")

    samples = np.concatenate(audio_chunks)
    # Encode to 16-bit PCM WAV using stdlib wave (no extra deps)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)   # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes((samples * 32767).astype(np.int16).tobytes())
    return buf.getvalue()


async def speak(text: str, voice: str = "af_heart") -> bytes:
    """Text-to-speech.

    Primary: kokoro on CPU — zero VRAM, 780M stays on chat model.
    Fallback: Lemonade Kokoro (causes model swap on 780M).
    """
    try:
        return await asyncio.to_thread(_speak_cpu, text, voice)
    except ImportError:
        LOG.debug("[lemonade] kokoro not installed — falling back to Lemonade TTS")
    except Exception as e:
        LOG.warning("[lemonade] CPU TTS failed: %s — falling back to Lemonade TTS", e)

    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(
            f"{LEMONADE_URL}/api/v1/audio/speech",
            json={"model": "kokoro", "input": text[:500], "voice": voice},
        )
        r.raise_for_status()
        return r.content


# ---------------------------------------------------------------------------
# Image gen — always Lemonade/780M (SD needs GPU)
# ---------------------------------------------------------------------------

async def generate_image(prompt: str, model: str | None = None,
                         size: str = "512x512") -> str:
    """Stable Diffusion image generation via Lemonade (780M iGPU).

    Returns base64 PNG string or URL depending on Lemonade version.
    Causes a model swap on 780M (~10s), unavoidable without a second GPU.
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


# ---------------------------------------------------------------------------
# Status — used by /avery/lemonade/status
# ---------------------------------------------------------------------------

async def lemonade_status() -> dict:
    available = await lemonade_available()
    models: list[str] = []
    if available:
        try:
            async with httpx.AsyncClient(timeout=3) as c:
                r = await c.get(f"{LEMONADE_URL}/api/v1/models")
                models = [m["id"] for m in r.json().get("data", [])]
        except Exception:
            pass

    cpu_whisper_ok = False
    cpu_kokoro_ok  = False
    try:
        import faster_whisper  # noqa
        cpu_whisper_ok = True
    except ImportError:
        pass
    try:
        import kokoro  # noqa
        cpu_kokoro_ok = True
    except ImportError:
        pass

    return {
        "available":         available,
        "url":               LEMONADE_URL,
        "chat_model":        _CHAT_MODEL,
        "image_model":       _IMAGE_MODEL,
        "models":            models,
        "cpu_stt":           cpu_whisper_ok,
        "cpu_tts":           cpu_kokoro_ok,
        "stt_backend":       "cpu:faster-whisper" if cpu_whisper_ok else "lemonade:whisper",
        "tts_backend":       "cpu:kokoro"          if cpu_kokoro_ok  else "lemonade:kokoro",
        "image_backend":     "lemonade:sdcpp",
    }
