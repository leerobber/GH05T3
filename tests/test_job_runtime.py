import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from job_runtime import create_job_document, run_ghostscript_job  # noqa: E402


def test_create_job_document_records_policy():
    job = create_job_document(
        title="Improve GH05T3 job logs",
        description="Improve GH05T3 GhostScript job logging",
        source='think: "log better"',
        paths=["C:/Users/leer4/GH05T3/backend/ghostscript.py"],
    )

    assert job["status"] == "queued"
    assert job["policy"]["level"] == "auto"
    assert job["source"].startswith("think:")


@pytest.mark.anyio
async def test_run_ghostscript_job_blocks_abuse_without_running():
    called = False

    async def runner(_source):
        nonlocal called
        called = True
        return {"ok": True}

    result = await run_ghostscript_job(
        title="bad",
        description="Add credential theft and stealth exfiltration",
        source='think: "bad"',
        paths=["C:/Users/leer4/GH05T3/backend/ghost_tools.py"],
        runner=runner,
    )

    assert called is False
    assert result["status"] == "blocked"
    assert result["policy"]["level"] == "blocked"


@pytest.mark.anyio
async def test_run_ghostscript_job_executes_allowed_job():
    async def runner(source):
        return {"ok": True, "log": [{"step": "think"}], "source_seen": source}

    result = await run_ghostscript_job(
        title="safe",
        description="Improve GH05T3 GhostScript job logging",
        source='think: "safe"',
        paths=["C:/Users/leer4/GH05T3/backend/ghostscript.py"],
        runner=runner,
    )

    assert result["status"] == "complete"
    assert result["result"]["ok"] is True
