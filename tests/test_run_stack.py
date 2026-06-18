"""Tests for run_stack.py — port review and frontend build validation."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from run_stack import (
    CORE_PORTS,
    INFERENCE_ENV,
    ROOT,
    SMOKE_CHECKS,
    _frontend_build_ok,
    _read_env,
    review_ports,
)

BUILD_DIR = ROOT / "frontend" / "build"
INDEX = BUILD_DIR / "index.html"


def test_core_ports_defined():
    assert CORE_PORTS["backend"] == 8001
    assert CORE_PORTS["gateway"] == 8002
    assert CORE_PORTS["frontend"] == 3210


def test_review_ports_shape():
    rows = review_ports()
    assert "mongo" in rows
    assert "port" in rows["mongo"]
    assert "listening" in rows["mongo"]
    assert isinstance(rows["mongo"]["listening"], bool)


def test_read_env_missing_key():
    assert _read_env("GH05T3_API_TOKEN_THAT_DOES_NOT_EXIST_XYZ") in ("",)


def test_frontend_build_ok_when_assets_present():
    if not INDEX.is_file():
        pytest.skip("frontend build not present — run: cd frontend && yarn build")
    assert _frontend_build_ok() is True


def test_frontend_build_ok_false_when_index_missing(tmp_path, monkeypatch):
    import run_stack

    fake_root = tmp_path
    monkeypatch.setattr(run_stack, "ROOT", fake_root)
    monkeypatch.setattr(run_stack, "BUILD_DIR", fake_root / "frontend" / "build")
    assert run_stack._frontend_build_ok() is False


def test_inference_env_has_windows_hf_flags():
    assert INFERENCE_ENV["GH05T3_FORCE_HF"] == "1"
    assert INFERENCE_ENV["HF_DEACTIVATE_ASYNC_LOAD"] == "1"


def test_smoke_checks_cover_core_services():
    names = {name for name, _, _ in SMOKE_CHECKS}
    assert {"gateway", "backend", "frontend", "inference", "oss"} <= names


def test_built_index_references_existing_assets():
    if not INDEX.is_file():
        pytest.skip("frontend build not present")
    html = INDEX.read_text(encoding="utf-8")
    refs = re.findall(r'/(assets/[^"\']+)', html)
    assert refs, "index.html should reference hashed assets"
    for ref in refs:
        assert (BUILD_DIR / ref.lstrip("/")).is_file(), f"missing asset: {ref}"