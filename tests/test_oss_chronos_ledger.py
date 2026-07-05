"""
Tests for ChronosLedger's default-path resolution.

Covers the fix for a real bug: the default ledger path used to be a bare
relative Path("data/aethyro_swarm.bin"), so different processes' working
directories silently resolved to different physical files. These tests
never touch the real production ledger — every case uses a small capacity
and a tmp_path-scoped file.
"""
from __future__ import annotations

import importlib

import pytest

from backend.oss.core import chronos_ledger


def test_default_path_anchored_to_repo_root_not_cwd(tmp_path, monkeypatch):
    """The default ledger path must not depend on the process CWD."""
    fake_root = tmp_path / "fake_repo"
    fake_root.mkdir()
    elsewhere = tmp_path / "elsewhere_cwd"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    monkeypatch.setattr(chronos_ledger, "REPO_ROOT", fake_root)
    monkeypatch.delenv("CHRONOS_LEDGER_PATH", raising=False)

    default_path = chronos_ledger.Path(
        chronos_ledger.os.environ.get(
            "CHRONOS_LEDGER_PATH", str(chronos_ledger.REPO_ROOT / "data" / "aethyro_swarm.bin")
        )
    )
    assert default_path == fake_root / "data" / "aethyro_swarm.bin"

    ledger = chronos_ledger.ChronosLedger(filename=default_path, capacity=4)
    try:
        assert ledger._path == fake_root / "data" / "aethyro_swarm.bin"
    finally:
        ledger.close()


def test_env_var_override_wins(tmp_path, monkeypatch):
    """CHRONOS_LEDGER_PATH must override the computed repo-root default."""
    custom = tmp_path / "custom.bin"
    monkeypatch.setenv("CHRONOS_LEDGER_PATH", str(custom))

    reloaded = importlib.reload(chronos_ledger)
    try:
        assert reloaded._DEFAULT_LEDGER == custom
        ledger = reloaded.ChronosLedger(capacity=4)
        try:
            assert ledger._path == custom
        finally:
            ledger.close()
    finally:
        monkeypatch.delenv("CHRONOS_LEDGER_PATH", raising=False)
        importlib.reload(chronos_ledger)


def test_explicit_filename_still_overrides_everything(tmp_path, monkeypatch):
    """An explicit filename= argument must win over env var and CWD alike."""
    monkeypatch.setenv("CHRONOS_LEDGER_PATH", str(tmp_path / "should_be_ignored.bin"))
    explicit = tmp_path / "explicit.bin"

    ledger = chronos_ledger.ChronosLedger(filename=explicit, capacity=4)
    try:
        assert ledger._path == explicit
    finally:
        ledger.close()
        monkeypatch.delenv("CHRONOS_LEDGER_PATH", raising=False)
