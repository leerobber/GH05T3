"""OSS monetization — Stripe → NC settlement tests."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_BACKEND = _ROOT / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))
if str(_ROOT) not in sys.path:
    sys.path.insert(1, str(_ROOT))

from oss.monetization.stripe import (
    PLAN_CREDITS,
    clear_settlements,
    settle_invoice_payment,
    settle_payment,
    settlement_status,
)


@pytest.fixture(autouse=True)
def _reset_settlements():
    clear_settlements()
    yield
    clear_settlements()


def test_plan_credits_defaults():
    assert PLAN_CREDITS["starter"] == 100
    assert PLAN_CREDITS["pro"] == 500
    assert PLAN_CREDITS["enterprise"] == 2000


@patch("oss.monetization.stripe.credit_agent", return_value=True)
def test_settle_payment_starter(mock_credit):
    result = settle_payment("cus_test_1", 29.0, "starter", "checkout.session.completed")

    assert result["ok"] is True
    assert result["credits"] == 100
    assert result["agent"] == "GH05T3-Avery"
    assert result["plan"] == "starter"
    mock_credit.assert_called_once()
    args = mock_credit.call_args[0]
    assert args[0] == "GH05T3-Avery"
    assert args[1] == 100.0
    assert "stripe:checkout.session.completed" in args[2]


@patch("oss.monetization.stripe.credit_agent", return_value=True)
def test_settle_payment_pro_plan(mock_credit):
    result = settle_payment("cus_pro", 99.0, "pro", "invoice.payment_succeeded")

    assert result["credits"] == 500
    assert result["plan"] == "pro"
    mock_credit.assert_called_once()
    assert mock_credit.call_args[0][1] == 500.0


@patch("oss.monetization.stripe.credit_agent", return_value=True)
def test_settle_payment_mapped_agent(mock_credit):
    with patch(
        "oss.monetization.stripe._get_subscriber_record",
        return_value={"plan": "enterprise", "agent": "FORGE"},
    ):
        result = settle_payment("cus_mapped", 199.0, "enterprise", "manual.test")

    assert result["agent"] == "FORGE"
    assert result["credits"] == 2000
    mock_credit.assert_called_once()
    assert mock_credit.call_args[0][:2] == ("FORGE", 2000.0)


@patch("oss.monetization.stripe.credit_agent", return_value=False)
def test_settle_payment_credit_failure(mock_credit):
    result = settle_payment("cus_fail", 10.0, "starter", "invoice.payment_succeeded")

    assert result["ok"] is False
    mock_credit.assert_called_once()


@patch("oss.monetization.stripe.credit_agent", return_value=True)
def test_settle_invoice_payment_wrapper(mock_credit):
    data = {
        "object": {
            "customer": "cus_inv_1",
            "amount_paid": 9900,
        }
    }
    with patch(
        "oss.monetization.stripe._get_subscriber_record",
        return_value={"plan": "pro"},
    ):
        result = settle_invoice_payment(data)

    assert result["customer_id"] == "cus_inv_1"
    assert result["amount_usd"] == 99.0
    assert result["credits"] == 500
    assert result["event_type"] == "invoice.payment_succeeded"
    mock_credit.assert_called_once()


@patch("oss.monetization.stripe.credit_agent", return_value=True)
def test_settlement_status_tracks_recent(mock_credit):
    settle_payment("cus_a", 10.0, "starter", "checkout.session.completed")
    settle_payment("cus_b", 20.0, "pro", "invoice.payment_succeeded")

    status = settlement_status()
    assert status["total"] == 2
    assert status["ok"] == 2
    assert status["failed"] == 0
    assert status["total_credits_settled"] == 600
    assert len(status["recent"]) == 2
    assert status["plan_credits"] == PLAN_CREDITS


@patch("oss.monetization.stripe.credit_agent", return_value=True)
def test_settlement_history_capped_at_100(mock_credit):
    for i in range(105):
        settle_payment(f"cus_{i}", 1.0, "starter", "manual.test")

    status = settlement_status()
    assert status["total"] == 100


@patch("oss.monetization.stripe.credit_agent", return_value=True)
def test_stripe_integration_checkout_settles(mock_credit, tmp_path):
    import importlib.util

    subs_file = tmp_path / "subscribers.json"
    mod_path = _BACKEND / "integrations" / "stripe_integration.py"
    spec = importlib.util.spec_from_file_location(
        "gh05t3_backend_stripe_integration",
        mod_path,
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod._SUBS_FILE = subs_file
    _handle_checkout_completed = mod._handle_checkout_completed

    data = {
        "object": {
            "customer": "cus_checkout",
            "customer_email": "test@example.com",
            "subscription": "sub_123",
            "metadata": {"plan": "pro"},
            "amount_total": 9900,
        }
    }
    result = _handle_checkout_completed(data)

    assert result["action"] == "subscriber_created"
    assert result["settlement"]["credits"] == 500
    mock_credit.assert_called_once()


@patch("oss.monetization.stripe.credit_agent", return_value=True)
def test_stripe_integration_invoice_settles(mock_credit):
    import importlib.util

    mod_path = _BACKEND / "integrations" / "stripe_integration.py"
    spec = importlib.util.spec_from_file_location(
        "gh05t3_backend_stripe_integration_invoice",
        mod_path,
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _handle_payment_succeeded = mod._handle_payment_succeeded

    data = {
        "object": {
            "customer": "cus_invoice",
            "amount_paid": 2900,
        }
    }
    with patch(
        "oss.monetization.stripe._get_subscriber_record",
        return_value={"plan": "starter"},
    ):
        result = _handle_payment_succeeded(data)

    assert result["action"] == "payment_received"
    assert result["settlement"]["credits"] == 100
    mock_credit.assert_called_once()