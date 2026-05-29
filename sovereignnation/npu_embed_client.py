"""
NPU Embedding Client — drop-in wrapper for any part of the Sovereign stack.

Usage (ChromaDB):
    from sovereignnation.npu_embed_client import NPUEmbedFunction
    collection = chroma_client.get_or_create_collection(
        name="agent_memory",
        embedding_function=NPUEmbedFunction(),
    )

Usage (raw):
    from sovereignnation.npu_embed_client import embed_texts, embed_query
    vecs  = embed_texts(["hello world", "agent task"])  # List[List[float]]
    vec   = embed_query("what is my balance?")          # List[float]

Usage (LangChain):
    from sovereignnation.npu_embed_client import NPULangChainEmbeddings
    embeddings = NPULangChainEmbeddings()

Service must be running at http://127.0.0.1:8111
Falls back to local sentence-transformers if service is down.
"""

from __future__ import annotations
import logging
import os
from typing import List, Optional

import httpx

log = logging.getLogger("npu_embed_client")

SERVICE_URL   = os.environ.get("NPU_EMBED_URL", "http://127.0.0.1:8111")
DEFAULT_MODEL = os.environ.get("NPU_EMBED_MODEL", "bge")   # "bge" | "minilm"
TIMEOUT       = 30.0   # seconds

# ─── Lazy fallback ────────────────────────────────────────────────────────────
_fallback_model = None

def _get_fallback():
    global _fallback_model
    if _fallback_model is not None:
        return _fallback_model
    try:
        from sentence_transformers import SentenceTransformer
        _fallback_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        log.warning("NPU service unavailable — using local MiniLM fallback")
    except Exception:
        _fallback_model = False
    return _fallback_model


def _fallback_embed(texts: List[str]) -> List[List[float]]:
    model = _get_fallback()
    if not model:
        raise RuntimeError("NPU embedding service is down and local MiniLM unavailable")
    vecs = model.encode(texts, normalize_embeddings=True)
    return vecs.tolist()


# ─── Core sync functions ──────────────────────────────────────────────────────
def embed_texts(
    texts: List[str],
    model: str = DEFAULT_MODEL,
    timeout: float = TIMEOUT,
) -> List[List[float]]:
    """Embed a batch of texts. Returns List[List[float]]."""
    if not texts:
        return []
    try:
        resp = httpx.post(
            f"{SERVICE_URL}/embed",
            json={"texts": texts, "model": model},
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json()["embeddings"]
    except Exception as e:
        log.warning("NPU embed service error (%s) — using fallback", e)
        return _fallback_embed(texts)


def embed_query(
    text: str,
    model: str = DEFAULT_MODEL,
    timeout: float = TIMEOUT,
) -> List[float]:
    """Embed a single query. Returns List[float]."""
    try:
        resp = httpx.post(
            f"{SERVICE_URL}/embed_query",
            json={"text": text, "model": model},
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json()["embedding"]
    except Exception as e:
        log.warning("NPU embed_query error (%s) — using fallback", e)
        return _fallback_embed([text])[0]


def service_health() -> dict:
    """Check embedding service health. Returns {} if down."""
    try:
        resp = httpx.get(f"{SERVICE_URL}/health", timeout=3.0)
        return resp.json()
    except Exception:
        return {}


# ─── ChromaDB embedding function ─────────────────────────────────────────────
class NPUEmbedFunction:
    """
    ChromaDB-compatible embedding function.

    Example:
        import chromadb
        from sovereignnation.npu_embed_client import NPUEmbedFunction

        client = chromadb.PersistentClient(path="./chroma_db")
        collection = client.get_or_create_collection(
            name="agent_memory",
            embedding_function=NPUEmbedFunction(model="bge"),
        )
        collection.add(documents=["doc1", "doc2"], ids=["id1", "id2"])
        results = collection.query(query_texts=["search query"], n_results=5)
    """

    def __init__(self, model: str = DEFAULT_MODEL):
        self.model = model

    def __call__(self, input: List[str]) -> List[List[float]]:
        return embed_texts(input, model=self.model)


# ─── LangChain embedding class ────────────────────────────────────────────────
class NPULangChainEmbeddings:
    """
    LangChain-compatible embedding class (implements Embeddings interface).
    Drop-in replacement for OpenAIEmbeddings, HuggingFaceEmbeddings, etc.

    Example:
        from langchain.vectorstores import FAISS
        from sovereignnation.npu_embed_client import NPULangChainEmbeddings

        embeddings = NPULangChainEmbeddings(model="bge")
        vectorstore = FAISS.from_texts(texts, embeddings)
        docs = vectorstore.similarity_search("query", k=5)
    """

    def __init__(self, model: str = DEFAULT_MODEL):
        self.model = model

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return embed_texts(texts, model=self.model)

    def embed_query(self, text: str) -> List[float]:
        return embed_query(text, model=self.model)


# ─── Async versions ───────────────────────────────────────────────────────────
async def async_embed_texts(
    texts: List[str],
    model: str = DEFAULT_MODEL,
    timeout: float = TIMEOUT,
) -> List[List[float]]:
    if not texts:
        return []
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{SERVICE_URL}/embed",
                json={"texts": texts, "model": model},
            )
            resp.raise_for_status()
            return resp.json()["embeddings"]
    except Exception as e:
        log.warning("async NPU embed error (%s) — using fallback", e)
        return _fallback_embed(texts)


async def async_embed_query(
    text: str,
    model: str = DEFAULT_MODEL,
    timeout: float = TIMEOUT,
) -> List[float]:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{SERVICE_URL}/embed_query",
                json={"text": text, "model": model},
            )
            resp.raise_for_status()
            return resp.json()["embedding"]
    except Exception as e:
        log.warning("async NPU embed_query error (%s) — using fallback", e)
        return _fallback_embed([text])[0]
