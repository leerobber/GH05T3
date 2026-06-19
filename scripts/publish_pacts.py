#!/usr/bin/env python3
"""
Publish Pact contracts to broker with retry/backoff.

Cross-platform usage:

Unix / Git Bash / WSL:
  PACT_BROKER_BASE_URL=... PACT_BROKER_TOKEN=... python scripts/publish_pacts.py pacts/ <version> [tag]

PowerShell (Windows):
  $env:PACT_BROKER_BASE_URL = "https://your-org.pactflow.io"
  $env:PACT_BROKER_TOKEN = "your-token"
  python scripts/publish_pacts.py pacts/ $(git rev-parse HEAD) ci

You can also put the values in a .env file in the repo root (requires python-dotenv).

Behavior:
- Exits 0 on success or when broker unreachable (after retries, logs warning).
- Uses consumer/version metadata (e.g. git SHA) for idempotency.
- Retries 3 times with exponential backoff (1s, 2s, 4s).
"""
import os
import sys
import time
import json
from pathlib import Path

import httpx

def broker_healthy(base_url: str, token: str | None) -> bool:
    try:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        with httpx.Client(timeout=5) as client:
            r = client.get(f"{base_url.rstrip('/')}/health", headers=headers)
            return r.status_code < 500
    except Exception:
        return False

def publish_pact(base_url: str, token: str, pact_file: Path, consumer_version: str, tag: str | None = None):
    url = f"{base_url.rstrip('/')}/pacts/provider/gh05t3-oss/consumer/gh05t3-gateway/version/{consumer_version}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    with open(pact_file, "rb") as f:
        data = f.read()

    with httpx.Client(timeout=30) as client:
        r = client.put(url, content=data, headers=headers)
        if r.status_code in (200, 201, 204):
            print(f"[pact] Published {pact_file.name} for version {consumer_version}")
            if tag:
                # Tag the version (optional, best effort)
                tag_url = f"{base_url.rstrip('/')}/pacticipants/gh05t3-gateway/versions/{consumer_version}/tags/{tag}"
                client.put(tag_url, headers=headers)
            return True
        else:
            print(f"[pact] Publish failed: {r.status_code} {r.text[:200]}")
            return False

def main():
    if len(sys.argv) < 3:
        print("Usage: publish_pacts.py <pacts_dir> <version> [tag]")
        sys.exit(2)

    pacts_dir = Path(sys.argv[1])
    version = sys.argv[2]
    tag = sys.argv[3] if len(sys.argv) > 3 else None

    # Support .env file if python-dotenv is installed (nice for Windows dev)
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    broker_url = os.environ.get("PACT_BROKER_BASE_URL") or os.environ.get("PACT_BROKER_URL")
    token = os.environ.get("PACT_BROKER_TOKEN")

    if not broker_url:
        print("[pact] No broker URL — skipping publish (no-op).")
        sys.exit(0)

    if not broker_healthy(broker_url, token):
        print("[pact] Broker unhealthy or unreachable — will retry with backoff.")

    pact_files = list(pacts_dir.glob("*.json")) if pacts_dir.exists() else []
    if not pact_files:
        print("[pact] No pact files found — nothing to publish.")
        sys.exit(0)

    for attempt in range(3):
        if broker_healthy(broker_url, token):
            success = True
            for pf in pact_files:
                if not publish_pact(broker_url, token, pf, version, tag):
                    success = False
            if success:
                print("[pact] All pacts published successfully.")
                sys.exit(0)
        backoff = (2 ** attempt)
        print(f"[pact] Attempt {attempt+1} failed. Sleeping {backoff}s...")
        time.sleep(backoff)

    print("[pact] Broker unreachable after retries — logging warning and continuing (exit 0).")
    sys.exit(0)

if __name__ == "__main__":
    main()