"""GH05T3 core configuration — reads environment variables."""
import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent.parent / ".env")

BACKENDS = {
    "primary":  os.environ.get("VLLM_PRIMARY_URL",    "http://localhost:8010"),
    "verifier": os.environ.get("LLAMA_VERIFIER_URL",  "http://localhost:8011"),
    "fallback":  os.environ.get("LLAMA_FALLBACK_URL", "http://localhost:8012"),
}

GATEWAY_HOST  = os.environ.get("GATEWAY_HOST",  "0.0.0.0")
GATEWAY_PORT  = int(os.environ.get("GATEWAY_PORT", "8002"))
GITHUB_PAT    = os.environ.get("GITHUB_PAT",    "")
GITHUB_REPO   = os.environ.get("GITHUB_REPO",   "leerobber/GH05T3")
GITHUB_BRANCH = os.environ.get("GITHUB_BRANCH", "main")

# Stripe — billing & subscriptions
STRIPE_SECRET_KEY     = os.environ.get("STRIPE_SECRET_KEY",     "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
