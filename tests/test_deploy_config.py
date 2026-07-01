"""Sprint 2 — deploy config validation."""
from __future__ import annotations

import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]


def test_vercel_json_valid():
    data = json.loads((_ROOT / "deploy" / "vercel.json").read_text(encoding="utf-8"))
    assert data["outputDirectory"] == "frontend/build"
    assert data["env"]["REACT_APP_GW3_URL"] == "https://api.aethyro.com"


def test_cloudflare_pages_toml_exists():
    text = (_ROOT / "deploy" / "cloudflare-pages.toml").read_text(encoding="utf-8")
    assert "aethyro-app" in text
    assert "api.aethyro.com" in text


def test_tunnel_config_ingress():
    text = (_ROOT / "deploy" / "tunnel-config.yml").read_text(encoding="utf-8")
    assert "api.aethyro.com" in text
    assert "app.aethyro.com" in text
    assert "8002" in text


def test_deploy_workflow_exists():
    # CI workflows removed — deploy is configured via vercel.json + cloudflare-pages.toml
    assert (_ROOT / "deploy" / "vercel.json").is_file()
    assert (_ROOT / "deploy" / "cloudflare-pages.toml").is_file()