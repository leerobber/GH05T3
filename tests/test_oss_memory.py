"""OSS memory facade tests."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def test_memory_status_returns_structure():
    from oss.adapters.memory import memory_status
    with patch("oss.adapters.memory.LOG"):
        status = memory_status()
    assert "palace" in status
    assert "cortex" in status
    assert "unified" in status


@pytest.mark.anyio
async def test_recall_unified_uses_cortex_when_available():
    from oss.adapters.memory import recall_unified
    mock_cortex = MagicMock()
    mock_cortex.read = AsyncMock(return_value="[user context]\nPrefers concise answers\n\n")
    mock_mod = MagicMock()
    mock_mod.get_cortex.return_value = mock_cortex
    with patch.dict(sys.modules, {"memory_cortex": mock_mod}):
        result = await recall_unified("billing setup", user_id="u1")
    assert result["count"] >= 1
    assert "cortex" in result["sources"]