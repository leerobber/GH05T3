"""Verify Vite bakes REACT_APP_* into production bundles."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
YARN = shutil.which("yarn")


@pytest.mark.skipif(
    not YARN or not (FRONTEND / "node_modules").is_dir(),
    reason="yarn or frontend node_modules not available",
)
def test_vite_bakes_react_app_gw3_url():
    env = os.environ.copy()
    env["REACT_APP_GW3_URL"] = "https://api.aethyro.com"
    proc = subprocess.run(
        "yarn build",
        cwd=str(FRONTEND),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        shell=True,
    )
    assert proc.returncode == 0, (proc.stderr or proc.stdout)[-500:]

    assets = list((FRONTEND / "build" / "assets").glob("index-*.js"))
    assert assets, "expected hashed JS bundle"
    bundle = assets[0].read_text(encoding="utf-8", errors="ignore")
    assert "api.aethyro.com" in bundle

    # Restore dev-default bundle for local run.bat
    subprocess.run("yarn build", cwd=str(FRONTEND), check=True, timeout=120, shell=True)