"""
SovereignNation Payments Service  v1.0
======================================
FastAPI service handling all Stripe interactions.

Endpoints:
  GET  /checkout?plan=professional   → creates Stripe Checkout Session, redirects
  POST /webhook                      → handles Stripe events (payment confirmed, etc.)
  GET  /portal?customer_id=...       → redirects to Stripe Customer Portal
  GET  /prices                       → returns current pricing JSON (for landing page)
  GET  /health                       → service health check

Run: uvicorn payments:app --host 0.0.0.0 --port 7862
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import secrets
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import stripe
import uvicorn
from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

# ── Config ────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent
ENV_FILE = ROOT / ".env.payments"

def _load_env():
    """Load .env.payments without requiring python-dotenv."""
    if not ENV_FILE.exists():
        return
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

_load_env()

STRIPE_SECRET_KEY    = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
PUBLISHABLE_KEY      = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
BASE_URL             = os.getenv("PAYMENTS_BASE_URL", "http://localhost:7861").rstrip("/")
PORTAL_ENABLED       = os.getenv("STRIPE_PORTAL_ENABLED", "0") == "1"
NOTIFY_EMAIL         = os.getenv("NOTIFY_EMAIL", "")
DATA_DIR             = ROOT.parent / "data"
DATA_DIR.mkdir(exist_ok=True)
PAYMENTS_LOG         = DATA_DIR / "payments.json"
CUSTOMERS_FILE       = DATA_DIR / "customers.json"   # subscription access registry

stripe.api_key = STRIPE_SECRET_KEY

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    handlers=[
        logging.FileHandler(DATA_DIR / "payments.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("payments")

# ── Pricing Catalogue ─────────────────────────────────────────────────────────
# These match what's shown on the landing page.
# unit_amount is in CENTS (Stripe standard).

PLANS = {
    "professional": {
        "label":       "SovereignNation Professional",
        "setup_cents": 249900,   # $2,499.00 — one-time setup & deployment
        "mo_cents":    29900,    # $299.00/month — ongoing subscription
        "description": "7 AI specialist modules, on-premises deployment, monthly support",
    },
    # Enterprise is custom — handled via email, not Stripe Checkout
}


def _build_checkout_params(plan: str) -> dict:
    """
    Stripe subscription mode: ALL line_items must be recurring.
    Setup fee is disclosed in the product description; billed separately via invoice.
    """
    p = PLANS[plan]
    setup_usd  = p["setup_cents"] // 100
    mo_usd     = p["mo_cents"]    // 100
    return {
        "line_items": [
            {
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": p["label"],
                        "description": (
                            f"7 AI specialist modules, on-premises deployment, monthly support. "
                            f"First invoice includes ${setup_usd:,} one-time setup & deployment fee."
                        ),
                    },
                    "unit_amount": p["mo_cents"],
                    "recurring": {"interval": "month"},
                },
                "quantity": 1,
            },
        ],
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _log_payment(event_type: str, data: dict):
    """Append a payment event to the local payments.json log."""
    record = {
        "ts":    datetime.now(timezone.utc).isoformat(),
        "event": event_type,
        **data,
    }
    existing = []
    if PAYMENTS_LOG.exists():
        try:
            existing = json.loads(PAYMENTS_LOG.read_text(encoding="utf-8"))
        except Exception:
            existing = []
    existing.append(record)
    PAYMENTS_LOG.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
    return record


def _stripe_ready() -> bool:
    return bool(STRIPE_SECRET_KEY and not STRIPE_SECRET_KEY.startswith("sk_test_REPLACE"))


# ── Customer Registry ─────────────────────────────────────────────────────────

def _load_customers() -> dict:
    if CUSTOMERS_FILE.exists():
        try:
            return json.loads(CUSTOMERS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_customers(customers: dict):
    CUSTOMERS_FILE.write_text(
        json.dumps(customers, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _generate_api_key(customer_id: str) -> str:
    """Deterministic but secret key derived from customer_id + a server secret."""
    secret = STRIPE_SECRET_KEY[-16:]   # last 16 chars of stripe key as server secret
    h = hashlib.sha256(f"{secret}:{customer_id}".encode()).hexdigest()[:32]
    return f"sn_live_{h}"


def _set_customer_status(
    customer_id: str,
    status: str,              # active | suspended | cancelled
    *,
    email: str = "",
    plan: str = "",
    subscription_id: str = "",
):
    """Update or create a customer record in customers.json."""
    customers = _load_customers()
    existing = customers.get(customer_id, {})
    now = datetime.now(timezone.utc).isoformat()

    if customer_id not in customers:
        # New customer — generate API key
        customers[customer_id] = {
            "customer_id":    customer_id,
            "email":          email or existing.get("email", ""),
            "plan":           plan or existing.get("plan", ""),
            "subscription_id": subscription_id or existing.get("subscription_id", ""),
            "api_key":        _generate_api_key(customer_id),
            "status":         status,
            "created_at":     now,
            "status_updated": now,
            "suspended_at":   now if status == "suspended" else None,
        }
        log.info("Customer registered: %s  status=%s  key=%s",
                 customer_id, status, customers[customer_id]["api_key"])
    else:
        customers[customer_id].update({
            "status":         status,
            "status_updated": now,
        })
        if email:
            customers[customer_id]["email"] = email
        if plan:
            customers[customer_id]["plan"] = plan
        if subscription_id:
            customers[customer_id]["subscription_id"] = subscription_id
        if status == "suspended":
            customers[customer_id]["suspended_at"] = now
        elif status == "active":
            customers[customer_id]["suspended_at"] = None
        log.info("Customer updated: %s  status=%s", customer_id, status)

    _save_customers(customers)
    return customers[customer_id]


def _lookup_key(api_key: str) -> dict | None:
    """Return customer record if the key is valid, None otherwise."""
    customers = _load_customers()
    for record in customers.values():
        if record.get("api_key") == api_key:
            return record
    return None


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="SovereignNation Payments", version="1.0.0", docs_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


# ── GET /health ───────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {
        "status":        "ok",
        "stripe_ready":  _stripe_ready(),
        "base_url":      BASE_URL,
        "portal_enabled": PORTAL_ENABLED,
    }


# ── GET /prices ───────────────────────────────────────────────────────────────
@app.get("/prices")
def prices():
    return {
        plan: {
            "setup_usd":   info["setup_cents"] / 100,
            "monthly_usd": info["mo_cents"]    / 100,
            "label":       info["label"],
        }
        for plan, info in PLANS.items()
    }


# ── GET /checkout ─────────────────────────────────────────────────────────────
@app.get("/checkout")
async def create_checkout(
    plan: str = Query("professional", description="Plan name"),
    request: Request = None,
):
    if not _stripe_ready():
        raise HTTPException(
            status_code=503,
            detail="Stripe is not configured yet. Add your STRIPE_SECRET_KEY to .env.payments",
        )

    if plan not in PLANS:
        raise HTTPException(status_code=400, detail=f"Unknown plan: {plan}")

    # Use tunnel URL if configured, otherwise mirror the request origin
    origin = BASE_URL or str(request.base_url).rstrip("/")

    try:
        params = _build_checkout_params(plan)
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="subscription",
            success_url=f"{origin}/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{origin}/cancel",
            allow_promotion_codes=True,
            billing_address_collection="auto",
            metadata={"plan": plan, "source": "landing_page"},
            **params,
        )
        log.info("Checkout session created: %s  plan=%s", session.id, plan)
        _log_payment("checkout.created", {"session_id": session.id, "plan": plan})
        return RedirectResponse(session.url, status_code=303)

    except stripe.StripeError as e:
        log.error("Stripe error creating checkout: %s", e)
        raise HTTPException(status_code=502, detail=str(e))


# ── POST /webhook ─────────────────────────────────────────────────────────────
@app.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="stripe-signature"),
):
    payload = await request.body()

    # Verify signature if webhook secret is configured
    if STRIPE_WEBHOOK_SECRET and not STRIPE_WEBHOOK_SECRET.startswith("whsec_REPLACE"):
        try:
            event = stripe.Webhook.construct_event(payload, stripe_signature, STRIPE_WEBHOOK_SECRET)
        except stripe.SignatureVerificationError:
            log.warning("Webhook signature verification FAILED")
            raise HTTPException(status_code=400, detail="Invalid signature")
    else:
        # Dev mode — no signature verification
        try:
            event = stripe.Event.construct_from(json.loads(payload), stripe.api_key)
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    etype = event["type"]
    obj   = event["data"]["object"]
    log.info("Webhook received: %s", etype)

    # ── checkout.session.completed ─────────────────────────────────────────
    if etype == "checkout.session.completed":
        customer_email = obj.get("customer_details", {}).get("email", "unknown")
        customer_id    = obj.get("customer")
        sub_id         = obj.get("subscription")
        plan           = obj.get("metadata", {}).get("plan", "professional")
        amount_total   = obj.get("amount_total", 0) / 100

        _log_payment("payment.completed", {
            "customer_email":  customer_email,
            "customer_id":     customer_id,
            "subscription_id": sub_id,
            "plan":            plan,
            "amount_usd":      amount_total,
        })

        # Register customer and generate access key
        cust = _set_customer_status(
            customer_id, "active",
            email=customer_email, plan=plan, subscription_id=sub_id,
        )
        api_key = cust["api_key"]

        log.info("=" * 60)
        log.info("  NEW PAYMENT — ACCESS GRANTED")
        log.info("  Customer : %s", customer_email)
        log.info("  Plan     : %s", plan)
        log.info("  Amount   : $%.2f", amount_total)
        log.info("  API Key  : %s", api_key)
        log.info("=" * 60)

        # TODO: send welcome email with api_key to customer_email

    # ── invoice.payment_succeeded (recurring monthly) ──────────────────────
    elif etype == "invoice.payment_succeeded":
        customer_email = obj.get("customer_email", "unknown")
        customer_id    = obj.get("customer", "")
        amount         = obj.get("amount_paid", 0) / 100
        invoice_url    = obj.get("hosted_invoice_url", "")
        _log_payment("invoice.paid", {
            "customer_email": customer_email,
            "amount_usd":     amount,
            "invoice_url":    invoice_url,
        })
        if customer_id:
            _set_customer_status(customer_id, "active", email=customer_email)
        log.info("Invoice paid — access confirmed: %s  $%.2f", customer_email, amount)

    # ── invoice.payment_failed ─────────────────────────────────────────────
    elif etype == "invoice.payment_failed":
        customer_email = obj.get("customer_email", "unknown")
        customer_id    = obj.get("customer", "")
        _log_payment("invoice.failed", {
            "customer_email": customer_email,
            "customer_id":    customer_id,
        })
        if customer_id:
            _set_customer_status(customer_id, "suspended", email=customer_email)
        log.warning("Invoice FAILED — access SUSPENDED: %s", customer_email)

    # ── customer.subscription.deleted (cancellation) ──────────────────────
    elif etype == "customer.subscription.deleted":
        customer_id = obj.get("customer")
        _log_payment("subscription.cancelled", {"customer_id": customer_id})
        if customer_id:
            _set_customer_status(customer_id, "cancelled")
        log.info("Subscription cancelled — access REVOKED: customer=%s", customer_id)

    return {"status": "ok"}


# ── GET /portal ───────────────────────────────────────────────────────────────
@app.get("/portal")
async def customer_portal(customer_id: str = Query(...)):
    """Redirect an existing customer to the Stripe Customer Portal."""
    if not _stripe_ready():
        raise HTTPException(status_code=503, detail="Stripe not configured")
    if not PORTAL_ENABLED:
        raise HTTPException(status_code=503, detail="Customer portal not enabled yet")
    try:
        session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=BASE_URL,
        )
        return RedirectResponse(session.url, status_code=303)
    except stripe.StripeError as e:
        raise HTTPException(status_code=502, detail=str(e))


# ── GET /verify-key ───────────────────────────────────────────────────────────
@app.get("/verify-key")
def verify_key(key: str = Query(...)):
    """
    Called by serve.py before proxying any /api/* request.
    Returns 200 + {valid:true, plan, email} if active.
    Returns 402 if suspended/cancelled.
    Returns 401 if key not found.
    """
    record = _lookup_key(key)
    if not record:
        raise HTTPException(status_code=401, detail="Invalid access key. Check your welcome email.")
    if record["status"] == "suspended":
        raise HTTPException(
            status_code=402,
            detail=(
                f"Account suspended — payment overdue. "
                f"Update your billing at {BASE_URL}/portal?customer_id={record['customer_id']} "
                f"or contact support@sovereignnation.ai"
            ),
        )
    if record["status"] == "cancelled":
        raise HTTPException(
            status_code=402,
            detail="Subscription cancelled. Contact sales@sovereignnation.ai to reactivate.",
        )
    return {
        "valid":   True,
        "plan":    record.get("plan", "professional"),
        "email":   record.get("email", ""),
        "customer_id": record.get("customer_id", ""),
    }


# ── GET /customers ─────────────────────────────────────────────────────────────
@app.get("/customers")
def list_customers():
    """Internal: view all customer records."""
    return _load_customers()


# ── GET /payments-log ─────────────────────────────────────────────────────────
@app.get("/payments-log")
def payments_log():
    """Internal: view all payment events (add auth before exposing publicly)."""
    if not PAYMENTS_LOG.exists():
        return []
    return json.loads(PAYMENTS_LOG.read_text(encoding="utf-8"))


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    log.info("SovereignNation Payments starting on port 7862")
    log.info("Stripe ready: %s", _stripe_ready())
    log.info("Base URL    : %s", BASE_URL)
    uvicorn.run("payments:app", host="0.0.0.0", port=7862, log_level="info")
