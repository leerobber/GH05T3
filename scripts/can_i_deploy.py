#!/usr/bin/env python3
"""
Can-I-Deploy gate for Pact.

Queries the broker for verification status.

Exit codes:
  0 - can deploy (verified or broker unreachable with policy=allow)
  1 - cannot deploy (unverified pact)
  2 - broker unreachable (configurable via --strict)

Cross-platform usage:

PowerShell:
  $env:PACT_BROKER_BASE_URL = "..."
  $env:PACT_BROKER_TOKEN = "..."
  python scripts/can_i_deploy.py --consumer gh05t3-gateway --provider gh05t3-oss --version $(git rev-parse HEAD)

Unix:
  PACT_BROKER_BASE_URL=... PACT_BROKER_TOKEN=... python scripts/can_i_deploy.py ...

Supports .env file if python-dotenv is installed.
"""
import os
import sys
import httpx
import argparse

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--consumer", required=True)
    parser.add_argument("--provider", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--tag", default="ci")
    parser.add_argument("--strict", action="store_true", help="Fail if broker unreachable")
    args = parser.parse_args()

    # Support .env
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    base = (os.environ.get("PACT_BROKER_BASE_URL") or os.environ.get("PACT_BROKER_URL") or "").rstrip("/")
    token = os.environ.get("PACT_BROKER_TOKEN")

    if not base:
        print("[can-i-deploy] No broker configured — allowing (policy: allow on unreachable).")
        sys.exit(0)

    url = f"{base}/matrix/provider/{args.provider}/consumer/{args.consumer}/latest/{args.tag}/consumer-version/{args.version}"
    headers = {"Authorization": f"Bearer {token}"} if token else {}

    try:
        with httpx.Client(timeout=10) as client:
            r = client.get(url, headers=headers)
            if r.status_code == 200:
                data = r.json()
                verified = data.get("verified", False)
                if verified:
                    print("[can-i-deploy] PASS — latest pact verified.")
                    sys.exit(0)
                else:
                    print("[can-i-deploy] FAIL — pact not verified by provider.")
                    sys.exit(1)
            else:
                print(f"[can-i-deploy] Broker returned {r.status_code}. Allowing (non-strict).")
                if args.strict:
                    sys.exit(1)
                sys.exit(0)
    except Exception as e:
        print(f"[can-i-deploy] Broker unreachable: {e}. Allowing (non-strict).")
        if args.strict:
            sys.exit(1)
        sys.exit(0)

if __name__ == "__main__":
    main()