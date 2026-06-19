#!/usr/bin/env python3
"""
Broker health check script for Pact.

Exits:
  0 - healthy or no URL configured (no-op)
  1 - unhealthy
  2 - no broker configured (treat as no-op for flows)
"""
import os
import sys
import httpx

def main():
    url = os.environ.get("PACT_BROKER_URL") or os.environ.get("PACT_BROKER_BASE_URL")
    if not url:
        print("[broker] No PACT_BROKER_URL configured — treating as no-op.")
        sys.exit(2)

    base = url.rstrip("/")
    health_url = f"{base}/health" if not base.endswith("/health") else base

    try:
        with httpx.Client(timeout=5.0) as client:
            r = client.get(health_url)
            if r.status_code < 500:
                print(f"[broker] Healthy: {health_url} -> {r.status_code}")
                sys.exit(0)
            else:
                print(f"[broker] Unhealthy: {r.status_code}")
                sys.exit(1)
    except Exception as e:
        print(f"[broker] Health check failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()