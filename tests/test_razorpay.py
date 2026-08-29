from __future__ import annotations

import hashlib
import hmac
import pytest

from payment_recovery.providers.razorpay.adapter import RazorpayProviderAdapter
from payment_recovery.providers.razorpay.signatures import (
    RazorpaySignatureVerificationError,
    verify_razorpay_signature,
)
from payment_recovery.models import LeakageType, FailureCategory


def test_verify_razorpay_signature_success():
    secret = "test_webhook_secret_key"
    body = b'{"event":"payment.failed","id":"evt_123"}'
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    assert verify_razorpay_signature(body, sig, secret) is True


def test_verify_razorpay_signature_mismatch():
    secret = "test_webhook_secret_key"
    body = b'{"event":"payment.failed"}'

    with pytest.raises(RazorpaySignatureVerificationError):
        verify_razorpay_signature(body, "invalid_sig", secret)


def test_normalize_razorpay_event():
    adapter = RazorpayProviderAdapter()
    payload = {
        "id": "evt_rzp_test_99",
        "event": "subscription.halted",
        "created_at": 1755940000,
        "payload": {
            "subscription": {
                "entity": {
                    "id": "sub_12345",
                    "customer_id": "cust_888",
                    "amount": 99900,
                    "currency": "INR",
                    "status": "halted",
                }
            }
        },
    }

    event = adapter.normalize_event(payload)
    assert event.event_id == "evt_rzp_test_99"
    assert event.provider == "razorpay"
    assert event.leakage_type == LeakageType.FAILED_SUBSCRIPTION
    assert event.amount == 999.0
    assert event.currency == "INR"
