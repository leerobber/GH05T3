# NPU Embedding Service -- port 8111
# Runs under: C:/Users/leer4/.conda/envs/ryzen-ai-1.7.0/python.exe
#
# Backends (priority order):
#   1. BGE-large ONNX via VitisAI EP  (NPU, if driver supports standalone EP)
#   2. BGE-large ONNX via CPU EP      (fallback, still fast, no GPU touch)
#   3. sentence-transformers MiniLM   (lightweight fallback, 384-dim)
#
# Routes:
#   GET  /health            -> service status (all backends + intent + whisper)
#   GET  /models            -> list of available model names
#   POST /embed             -> {"texts": [...], "model": "bge"|"minilm"} -> embeddings
#   POST /embed_query       -> {"text": "...", "model": "bge"} -> single embedding
#   POST /transcribe        -> multipart audio file -> {"text":..., "language":..., "latency_ms":...}
#   POST /intent            -> {"query": "...", "model": "minilm"} -> {"agent":..., "confidence":..., "scores":...}

from __future__ import annotations
import io
import logging
import os
import shutil
import tempfile
import time
from typing import Dict, List, Optional

import numpy as np
import uvicorn
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ─── Paths ────────────────────────────────────────────────────────────────────
BGE_ONNX      = r"C:\Users\leer4\RyzenAI-SW\RyzenAI-SW-main\LLM-examples\RAG-OGA\bge-large-en-v1.5.onnx"
VAIML_CONFIG  = r"C:\Users\leer4\RyzenAI-SW\RyzenAI-SW-main\Transformer-examples\DistilBERT_text_classification_bf16\vitisai_config.json"
BGE_TOKENIZER = "BAAI/bge-large-en-v1.5"
MINILM_MODEL  = "sentence-transformers/all-MiniLM-L6-v2"
WHISPER_SIZE  = "base"   # tiny/base/small — base is fast + accurate enough

log = logging.getLogger("npu_embed")
logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-7s  %(message)s")

app = FastAPI(title="NPU Embedding Service", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

# ─── State ────────────────────────────────────────────────────────────────────
_bge_session   = None   # onnxruntime InferenceSession
_bge_tokenizer = None   # transformers AutoTokenizer
_bge_backend   = None   # "npu" | "cpu"
_bge_dim       = 1024

_minilm_model  = None   # SentenceTransformer
_minilm_dim    = 384

_whisper_model = None   # openai-whisper (lazy-loaded on first /transcribe call)

# Prototype embeddings per agent — computed at startup from representative phrases
_intent_prototypes: Dict[str, np.ndarray] = {}

# ─── Intent prototype phrases per agent ───────────────────────────────────────
INTENT_PHRASES: Dict[str, List[str]] = {
    "oracle": [
        "analyze this business data and provide insights",
        "what are the key trends and patterns in this information",
        "summarize the financial performance and metrics",
        "market analysis and competitive landscape overview",
        "interpret these numbers and explain what they mean",
        "give me a data-driven assessment of the situation",
        "what does the data say about our performance",
    ],
    "forge": [
        "identify the hidden risks and vulnerabilities in this plan",
        "what could go wrong and what are the worst case scenarios",
        "risk assessment covering threats liabilities and exposures",
        "expose weaknesses leverage points and blind spots",
        "what are the dangers pitfalls and legal liabilities",
        "find what was missed — the risks and threats and downside",
        "what is the biggest risk here and how serious is it",
    ],
    "codex": [
        "write code to implement this feature or automation",
        "build a script that does this task programmatically",
        "debug and fix this code or technical problem",
        "create a program workflow or technical solution",
        "implement this in Python or another programming language",
        "what is the technical implementation for this system",
        "generate the code for this business logic",
    ],
    "nexus": [
        "create an executive summary with strategic recommendations",
        "provide the next steps and 48 hour action plan",
        "synthesize all findings into a final board-level brief",
        "what should we do first based on all the analysis done",
        "give me the decisive strategic playbook to execute now",
        "turn all insights into concrete prioritized actions",
        "what is the strategic recommendation and timeline",
    ],
}


# ─── Init: BGE ────────────────────────────────────────────────────────────────
def _init_bge():
    global _bge_session, _bge_tokenizer, _bge_backend
    try:
        import onnxruntime as ort
        from transformers import AutoTokenizer

        if not os.path.exists(BGE_ONNX):
            log.warning("BGE ONNX not found at %s — skipping BGE", BGE_ONNX)
            return

        _bge_tokenizer = AutoTokenizer.from_pretrained(BGE_TOKENIZER)

        providers = ort.get_available_providers()
        if "VitisAIExecutionProvider" in providers and os.path.exists(VAIML_CONFIG):
            try:
                _bge_session = ort.InferenceSession(
                    BGE_ONNX,
                    providers=["VitisAIExecutionProvider"],
                    provider_options=[{
                        "config_file": VAIML_CONFIG,
                        "cache_dir": r"C:\Users\leer4\RyzenAI-SW\npu_cache",
                        "cacheKey": "bge_large_en_v1.5",
                    }],
                )
                _bge_backend = "npu"
                log.info("BGE-large loaded on NPU via VitisAI EP")
                return
            except Exception as e:
                log.warning("VitisAI EP failed (%s) — CPU fallback", e)

        _bge_session = ort.InferenceSession(BGE_ONNX, providers=["CPUExecutionProvider"])
        _bge_backend = "cpu"
        log.info("BGE-large loaded on CPU (%.1f MB)", os.path.getsize(BGE_ONNX) / 1e6)

    except Exception as e:
        log.error("BGE init failed: %s", e)


# ─── Init: MiniLM ─────────────────────────────────────────────────────────────
def _init_minilm():
    global _minilm_model
    try:
        from sentence_transformers import SentenceTransformer
        _minilm_model = SentenceTransformer(MINILM_MODEL)
        log.info("MiniLM-L6-v2 loaded (384-dim, CPU)")
    except Exception as e:
        log.warning("MiniLM init failed: %s", e)


# ─── Init: Intent prototypes ──────────────────────────────────────────────────
def _init_intent_prototypes():
    """Pre-compute mean prototype embedding for each agent category."""
    global _intent_prototypes
    if _minilm_model is None and _bge_session is None:
        log.warning("No embedding backend available — intent prototypes skipped")
        return

    t0 = time.perf_counter()
    for agent, phrases in INTENT_PHRASES.items():
        try:
            # Prefer MiniLM for intent (fast, reliable, always CPU)
            if _minilm_model is not None:
                vecs = np.array(_embed_minilm(phrases))
            else:
                vecs = np.array(_embed_bge(phrases))
            # Mean pool across phrases, then re-normalize
            mean_vec = vecs.mean(axis=0)
            norm = np.linalg.norm(mean_vec) + 1e-9
            _intent_prototypes[agent] = mean_vec / norm
        except Exception as e:
            log.warning("Prototype for '%s' failed: %s", agent, e)

    elapsed_ms = (time.perf_counter() - t0) * 1000
    log.info(
        "Intent prototypes ready for %d agents in %.0fms: %s",
        len(_intent_prototypes), elapsed_ms, list(_intent_prototypes.keys()),
    )


# ─── Embedding helpers ────────────────────────────────────────────────────────
def _embed_bge(texts: List[str]) -> List[List[float]]:
    if _bge_session is None or _bge_tokenizer is None:
        raise RuntimeError("BGE not initialized")
    results = []
    for text in texts:
        inputs = _bge_tokenizer(
            text, max_length=512, padding="max_length",
            truncation=True, return_tensors="np", return_token_type_ids=False,
        )
        onnx_in = {
            "input_ids":      inputs["input_ids"].astype(np.int64),
            "attention_mask": inputs["attention_mask"].astype(np.int64),
        }
        out = _bge_session.run(None, onnx_in)
        vec = out[1][0]                            # pooler_output (1, 1024)
        results.append((vec / (np.linalg.norm(vec) + 1e-9)).tolist())
    return results


def _embed_minilm(texts: List[str]) -> List[List[float]]:
    if _minilm_model is None:
        raise RuntimeError("MiniLM not initialized")
    return _minilm_model.encode(texts, normalize_embeddings=True).tolist()


def _resolve_backend(model_name: Optional[str]):
    """Return (embed_fn, dim, backend_label) for the requested model name."""
    if model_name == "minilm":
        if _minilm_model is None:
            raise HTTPException(503, "MiniLM not available")
        return _embed_minilm, _minilm_dim, "cpu", "minilm"
    else:
        if _bge_session is not None:
            return _embed_bge, _bge_dim, _bge_backend, "bge"
        if _minilm_model is not None:
            return _embed_minilm, _minilm_dim, "cpu", "minilm:fallback"
        raise HTTPException(503, "No embedding backend available")


# ─── Pydantic models ──────────────────────────────────────────────────────────
class EmbedRequest(BaseModel):
    texts: List[str]
    model: Optional[str] = "bge"


class EmbedQueryRequest(BaseModel):
    text: str
    model: Optional[str] = "bge"


class EmbedResponse(BaseModel):
    embeddings: List[List[float]]
    model: str
    dim: int
    backend: str
    latency_ms: float


class EmbedQueryResponse(BaseModel):
    embedding: List[float]
    model: str
    dim: int
    backend: str
    latency_ms: float


class TranscribeResponse(BaseModel):
    text: str
    language: Optional[str] = None
    latency_ms: float


class IntentRequest(BaseModel):
    query: str
    model: Optional[str] = "minilm"


class IntentResponse(BaseModel):
    agent: str
    confidence: float
    scores: Dict[str, float]
    latency_ms: float


# ─── Routes: embeddings ───────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {
        "status":         "ok",
        "bge_ready":      _bge_session is not None,
        "bge_backend":    _bge_backend,
        "bge_dim":        _bge_dim,
        "minilm_ready":   _minilm_model is not None,
        "minilm_dim":     _minilm_dim,
        "whisper_ready":  _whisper_model is not None,
        "whisper_model":  WHISPER_SIZE if _whisper_model else "not_loaded",
        "intent_ready":   len(_intent_prototypes) > 0,
        "intent_agents":  list(_intent_prototypes.keys()),
    }


@app.get("/models")
def list_models():
    available = []
    if _bge_session is not None:
        available.append({"name": "bge", "model": BGE_TOKENIZER, "dim": _bge_dim, "backend": _bge_backend})
    if _minilm_model is not None:
        available.append({"name": "minilm", "model": MINILM_MODEL, "dim": _minilm_dim, "backend": "cpu"})
    if _whisper_model is not None:
        available.append({"name": "whisper", "model": f"whisper-{WHISPER_SIZE}", "dim": None, "backend": "cpu"})
    return {"models": available}


@app.post("/embed", response_model=EmbedResponse)
def embed(req: EmbedRequest):
    if not req.texts:
        raise HTTPException(400, "texts must not be empty")
    t0 = time.perf_counter()
    try:
        fn, dim, backend, model_label = _resolve_backend(req.model)
        vecs = fn(req.texts)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Embedding error: {e}") from e
    return EmbedResponse(
        embeddings=vecs, model=model_label, dim=dim,
        backend=backend, latency_ms=round((time.perf_counter() - t0) * 1000, 2),
    )


@app.post("/embed_query", response_model=EmbedQueryResponse)
def embed_query(req: EmbedQueryRequest):
    result = embed(EmbedRequest(texts=[req.text], model=req.model))
    return EmbedQueryResponse(
        embedding=result.embeddings[0], model=result.model,
        dim=result.dim, backend=result.backend, latency_ms=result.latency_ms,
    )


# ─── Route: transcription ─────────────────────────────────────────────────────
@app.post("/transcribe", response_model=TranscribeResponse)
async def transcribe(file: UploadFile = File(...)):
    """
    Transcribe audio with Whisper (CPU device — zero GPU impact on LLM inference).
    Accepts WAV, MP3, M4A, OGG, FLAC, or any ffmpeg-decodable format.
    Whisper is lazy-loaded on the first call (~2s one-time delay).
    """
    global _whisper_model

    if _whisper_model is None:
        try:
            import whisper
            log.info("Lazy-loading Whisper '%s' (first call)...", WHISPER_SIZE)
            t_load = time.perf_counter()
            _whisper_model = whisper.load_model(WHISPER_SIZE, device="cpu")
            log.info("Whisper loaded in %.1fs", time.perf_counter() - t_load)
        except ImportError:
            raise HTTPException(503, "openai-whisper not installed in ryzen-ai env")
        except Exception as e:
            raise HTTPException(503, f"Whisper load failed: {e}") from e

    suffix = os.path.splitext(file.filename or "audio.wav")[1] or ".wav"
    t0 = time.perf_counter()
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name

        result   = _whisper_model.transcribe(tmp_path, fp16=False)
        text     = result.get("text", "").strip()
        language = result.get("language")
    except Exception as e:
        raise HTTPException(500, f"Transcription failed: {e}") from e
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

    return TranscribeResponse(
        text=text, language=language,
        latency_ms=round((time.perf_counter() - t0) * 1000, 2),
    )


# ─── Route: intent router ─────────────────────────────────────────────────────
@app.post("/intent", response_model=IntentResponse)
def intent_route(req: IntentRequest):
    """
    Route a user query to the best pipeline agent using cosine similarity
    against pre-computed prototype embeddings.
    Returns agent name (oracle / forge / codex / nexus), confidence, and all scores.
    """
    if not _intent_prototypes:
        raise HTTPException(503, "Intent prototypes not ready — embedding backend unavailable at startup")

    t0 = time.perf_counter()
    try:
        fn, _, _, _ = _resolve_backend(req.model or "minilm")
        raw_vec = np.array(fn([req.query])[0])
        query_vec = raw_vec / (np.linalg.norm(raw_vec) + 1e-9)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Query embedding failed: {e}") from e

    scores: Dict[str, float] = {}
    for agent, proto in _intent_prototypes.items():
        if proto.shape[0] != query_vec.shape[0]:
            log.warning("Dim mismatch agent='%s' proto=%d query=%d", agent, proto.shape[0], query_vec.shape[0])
            scores[agent] = 0.0
        else:
            scores[agent] = float(np.dot(query_vec, proto))

    best_agent = max(scores, key=lambda k: scores[k])

    # Confidence: softmax-style relative share of the winning score
    arr = np.array(list(scores.values()))
    shifted = arr - arr.min()
    confidence = float(shifted[list(scores.keys()).index(best_agent)] / (shifted.sum() + 1e-9))

    return IntentResponse(
        agent=best_agent,
        confidence=round(confidence, 4),
        scores={k: round(v, 4) for k, v in scores.items()},
        latency_ms=round((time.perf_counter() - t0) * 1000, 2),
    )


# ─── Startup ──────────────────────────────────────────────────────────────────
@app.on_event("startup")
def startup():
    log.info("Initializing embedding backends...")
    _init_bge()
    _init_minilm()
    _init_intent_prototypes()
    log.info(
        "Ready — BGE:%s(%s)  MiniLM:%s  Intent:%s  Whisper:lazy",
        "✓" if _bge_session else "✗", _bge_backend or "n/a",
        "✓" if _minilm_model else "✗",
        "✓(%d agents)" % len(_intent_prototypes) if _intent_prototypes else "✗",
    )


if __name__ == "__main__":
    uvicorn.run(
        "npu_embedding_service:app",
        host="127.0.0.1",
        port=8111,
        log_level="info",
    )
