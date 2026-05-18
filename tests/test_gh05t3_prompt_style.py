import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from gh05t3_state import GH05T3_SYSTEM_PROMPT  # noqa: E402


def test_prompt_keeps_progress_updates_sparse():
    prompt = GH05T3_SYSTEM_PROMPT.lower()

    assert "do not narrate every internal step" in prompt
    assert "calm and sparse" in prompt


def test_prompt_allows_requested_status_updates():
    prompt = GH05T3_SYSTEM_PROMPT.lower()

    assert "when robert asks for status" in prompt
    assert "status updates are allowed and encouraged" in prompt
