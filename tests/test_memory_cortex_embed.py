"""Unit tests for memory_cortex embedding dimension reconciliation."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

_BACKEND = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


def _mock_collection(
    *,
    embed_dim: int | None = None,
    count: int = 0,
    peek_dim: int | None = None,
) -> MagicMock:
    col = MagicMock()
    col.metadata = {"embed_dim": embed_dim} if embed_dim is not None else {}
    col.count.return_value = count
    if peek_dim is not None:
        col.peek.return_value = {"embeddings": [[0.0] * peek_dim]}
    else:
        col.peek.return_value = {"embeddings": []}
    return col


def test_collection_needs_recreate_metadata_mismatch():
    import memory_cortex as mc

    col = _mock_collection(embed_dim=768, count=3)
    assert mc._collection_needs_recreate(col, 384) is True


def test_collection_needs_recreate_metadata_match():
    import memory_cortex as mc

    col = _mock_collection(embed_dim=384, count=3)
    assert mc._collection_needs_recreate(col, 384) is False


def test_collection_needs_recreate_legacy_vectors_without_metadata():
    import memory_cortex as mc

    col = _mock_collection(embed_dim=None, count=2, peek_dim=768)
    assert mc._collection_needs_recreate(col, 384) is True


def test_collection_needs_recreate_empty_collection_stamps_metadata():
    import memory_cortex as mc

    col = _mock_collection(embed_dim=None, count=0)
    assert mc._collection_needs_recreate(col, 384) is True


def test_is_dim_mismatch_error():
    import memory_cortex as mc

    assert mc._is_dim_mismatch_error(Exception("Collection expecting 768, got 384"))
    assert not mc._is_dim_mismatch_error(Exception("connection refused"))


@pytest.mark.anyio
async def test_ensure_chroma_col_recreates_on_dim_mismatch():
    import memory_cortex as mc
    from embeddings import EmbedResult

    old_col = _mock_collection(embed_dim=768, count=5)
    new_col = MagicMock()
    new_col.metadata = {"embed_dim": 384}
    client = MagicMock()
    client.delete_collection = MagicMock()
    client.create_collection.return_value = new_col

    probe = EmbedResult(np.zeros(384, dtype=np.float32), "local:minilm", 384)

    with patch.object(mc, "_chroma_col", old_col), patch.object(mc, "_chroma_client", client), patch.object(
        mc, "_embed_dim_cache", 384
    ), patch.object(mc, "embed_semantic", AsyncMock(return_value=probe)):
        result = await mc._ensure_chroma_col()

    client.delete_collection.assert_called_once_with(name=mc.COLLECTION)
    client.create_collection.assert_called_once_with(
        name=mc.COLLECTION,
        metadata={"hnsw:space": "cosine", "embed_dim": 384},
    )
    assert result is new_col


@pytest.mark.anyio
async def test_ensure_chroma_col_keeps_matching_collection():
    import memory_cortex as mc

    col = _mock_collection(embed_dim=384, count=2)
    client = MagicMock()

    with patch.object(mc, "_chroma_col", col), patch.object(mc, "_chroma_client", client), patch.object(
        mc, "_embed_dim_cache", 384
    ):
        result = await mc._ensure_chroma_col()

    client.delete_collection.assert_not_called()
    client.create_collection.assert_not_called()
    assert result is col


@pytest.mark.anyio
async def test_search_recall_falls_back_to_query_texts_on_dim_mismatch():
    import memory_cortex as mc
    from embeddings import EmbedResult

    col = _mock_collection(embed_dim=768, count=1)
    col.query.return_value = {
        "documents": [["legacy memory"]],
        "metadatas": [[{"agent_id": "a1", "importance": 0.6}]],
        "distances": [[0.2]],
    }

    embed = EmbedResult(np.ones(384, dtype=np.float32), "local:minilm", 384)
    cortex = mc.MemoryCortex()

    with patch.object(mc, "_ensure_chroma_col", AsyncMock(return_value=col)), patch.object(
        mc, "_embed", AsyncMock(return_value=embed)
    ):
        hits = await cortex._search_recall("user1", "billing", "agent", k=3)

    col.query.assert_called_once()
    call_kwargs = col.query.call_args.kwargs
    assert "query_texts" in call_kwargs
    assert call_kwargs["query_texts"] == ["billing"]
    assert "query_embeddings" not in call_kwargs
    assert len(hits) == 1
    assert hits[0]["content"] == "legacy memory"