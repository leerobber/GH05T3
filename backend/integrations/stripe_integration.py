"""
GH05T3 / Avery — Stripe Integration
=====================================

Handles incoming Stripe webhooks and manages subscriber state.
Emits events onto the SwarmBus so Kai (NEXUS) and the rest of the
team can react to subscription changes in real time.

Env vars required:
    STRIPE_SECRET_KEY      — sk_live_... or sk_test_...
    STRIPE_WEBHOOK_SECRET  — whsec_... (from Stripe Dashboard → Webhooks)

Supported events:
    checkout.session.completed      → grant access
    customer.subscription.created   → activate subscriber
    customer.subscription.updated   → handle plan change
    customer.subscription.deleted   → deactivate subscriber
    invoice.payment_succeeded       → log successful payment
    invoice.payment_failed          → flag account, notify team
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import time
from pathlib import Path
from typing import Optional

log = logging.getLogger("gh0st3.stripe")

STRIPE_SECRET_KEY     = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

# Lightweight subscriber store — JSON file on disk.
# Replace with a DB when you have paying users at scale.
_SUBS_FILE = Path("data/subscribers.json")


def _load_subs() -> dict:
    _SUBS_FILE.parent.mkdir(parents=True, exist_ok=True)
    if _SUBS_FILE.exists():
        try:
            return json.loads(_SUBS_FILE.read_text())
        except Exception:
            return {}
    return {}


def _save_subs(subs: dict) -> None:
    _SUBS_FILE.write_text(json.dumps(subs, indent=2))


# ─────────────────────────────────────────────
# SIGNATURE VERIFICATION
# ─────────────────────────────────────────────

def verify_stripe_signature(payload: bytes, sig_header: str, secret: str) -> bool:
    """
    Validates Stripe webhook signature (t=timestamp,v1=hash format).
    Returns False if invalid — caller must return 400.
    """
    try:
        parts = {k: v for k, v in (p.split("=", 1) for p in sig_header.split(","))}
        ts    = parts.get("t", "")
        v1    = parts.get("v1", "")
        if not ts or not v1:
            return False

        # Reject replays older than 5 minutes
        if abs(time.time() - int(ts)) > 300:
            log.warning("Stripe webhook timestamp too old — possible replay attack")
            return False

        signed_payload = f"{ts}.".encode() + payload
        expected = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, v1)
    except Exception as e:
        log.error("Stripe signature verification error: %s", e)
        return False


# ─────────────────────────────────────────────
# EVENT HANDLERS
# ─────────────────────────────────────────────

def _handle_checkout_completed(data: dict) -> dict:
    session      = data.get("object", {})
    customer_id  = session.get("customer")
    customer_email = session.get("customer_email") or session.get("customer_details", {}).get("email", "")
    sub_id       = session.get("subscription")
    plan         = session.get("metadata", {}).get("plan", "starter")

    subs = _load_subs()
    subs[customer_id] = {
        "email":          customer_email,
        "subscription_id": sub_id,
        "plan":           plan,
        "status":         "active",
        "created_at":     time.time(),
        "updated_at":     time.time(),
    }
    _save_subs(subs)
    log.info("New subscriber: %s (%s) — plan: %s", customer_email, customer_id, plan)
    return {"action": "subscriber_created", "customer": customer_id, "plan": plan}


def _handle_subscription_created(data: dict) -> dict:
    sub         = data.get("object", {})
    customer_id = sub.get("customer")
    plan        = sub.get("items", {}).get("data", [{}])[0].get("price", {}).get("nickname", "starter")

    subs = _load_subs()
    if customer_id in subs:
        subs[customer_id]["status"]     = "active"
        subs[customer_id]["plan"]       = plan
        subs[customer_id]["updated_at"] = time.time()
        _save_subs(subs)
    return {"action": "subscription_activated", "customer": customer_id}


def _handle_subscription_updated(data: dict) -> dict:
    sub         = data.get("object", {})
    customer_id = sub.get("customer")
    status      = sub.get("status", "active")
    plan        = sub.get("items", {}).get("data", [{}])[0].get("price", {}).get("nickname", "starter")

    subs = _load_subs()
    if customer_id in subs:
        subs[customer_id]["status"]     = status
        subs[customer_id]["plan"]       = plan
        subs[customer_id]["updated_at"] = time.time()
        _save_subs(subs)
    return {"action": "subscription_updated", "customer": customer_id, "status": status}


def _handle_subscription_deleted(data: dict) -> dict:
    sub         = data.get("object", {})
    customer_id = sub.get("customer")

    subs = _load_subs()
    if customer_id in subs:
        subs[customer_id]["status"]     = "cancelled"
        subs[customer_id]["updated_at"] = time.time()
        _save_subs(subs)
    log.info("Subscriber cancelled: %s", customer_id)
    return {"action": "subscriber_cancelled", "customer": customer_id}


def _handle_payment_succeeded(data: dict) -> dict:
    inv         = data.get("object", {})
    customer_id = inv.get("customer")
    amount      = inv.get("amount_paid", 0) / 100
    return {"action": "payment_received", "customer": customer_id, "amount_usd": amount}


def _handle_payment_failed(data: dict) -> dict:
    inv         = data.get("object", {})
    customer_id = inv.get("customer")
    subs = _load_subs()
    if customer_id in subs:
        subs[customer_id]["status"]     = "past_due"
        subs[customer_id]["updated_at"] = time.time()
        _save_subs(subs)
    log.warning("Payment failed for customer: %s", customer_id)
    return {"action": "payment_failed", "customer": customer_id}


_HANDLERS = {
    "checkout.session.completed":     _handle_checkout_completed,
    "customer.subscription.created":  _handle_subscription_created,
    "customer.subscription.updated":  _handle_subscription_updated,
    "customer.subscription.deleted":  _handle_subscription_deleted,
    "invoice.payment_succeeded":      _handle_payment_succeeded,
    "invoice.payment_failed":         _handle_payment_failed,
}


def process_stripe_event(event_type: str, data: dict) -> Optional[dict]:
    """Dispatch a verified Stripe event to the appropriate handler."""
    handler = _HANDLERS.get(event_type)
    if handler:
        try:
            return handler(data)
        except Exception as e:
            log.error("Error processing Stripe event %s: %s", event_type, e)
            return {"action": "error", "event": event_type, "error": str(e)}
    log.debug("Unhandled Stripe event type: %s", event_type)
    return None


# ─────────────────────────────────────────────
# SUBSCRIBER QUERIES
# ─────────────────────────────────────────────

def get_subscriber(customer_id: str) -> Optional[dict]:
    return _load_subs().get(customer_id)


def is_active_subscriber(customer_id: str) -> bool:
    sub = get_subscriber(customer_id)
    return sub is not None and sub.get("status") == "active"


def all_subscribers() -> dict:
    return _load_subs()


def subscriber_count() -> dict:
    subs   = _load_subs()
    active = sum(1 for s in subs.values() if s.get("status") == "active")
    return {"total": len(subs), "active": active, "cancelled": len(subs) - active}
