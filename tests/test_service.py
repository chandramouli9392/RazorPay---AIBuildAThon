import hashlib
import hmac
import json
import time

import pytest
from fastapi.testclient import TestClient

from payment_recovery import service
from payment_recovery.state_machine import RecoveryStore

SECRET = "whsec_unit_test"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", SECRET)
    monkeypatch.setattr(service, "store", RecoveryStore())
    return TestClient(service.app)


def event(event_id="evt_1", event_type="payment_intent.payment_failed"):
    return {
        "id": event_id,
        "type": event_type,
        "created": 1_786_277_600,
        "data": {
            "object": {
                "id": "pi_1",
                "last_payment_error": {
                    "code": "card_declined",
                    "decline_code": "insufficient_funds",
                },
            }
        },
    }


def signed_request(client, payload, *, body_override=None):
    body = body_override if body_override is not None else json.dumps(payload).encode()
    timestamp = int(time.time())
    signature = hmac.new(
        SECRET.encode(), str(timestamp).encode() + b"." + body, hashlib.sha256
    ).hexdigest()
    return client.post(
        "/webhooks/stripe",
        content=body,
        headers={"Stripe-Signature": f"t={timestamp},v1={signature}"},
    )


def test_signed_failure_and_replay(client):
    first = signed_request(client, event())
    replay = signed_request(client, event())
    assert first.status_code == 200
    assert first.json()["case"]["status"] == "pending"
    assert first.json()["notification_required"] is True
    assert replay.json()["duplicate"] is True


def test_success_cancels_scheduled_retry(client):
    assert signed_request(client, event()).status_code == 200
    success = signed_request(client, event("evt_success", "payment_intent.succeeded"))
    assert success.json()["case"]["status"] == "recovered"
    assert success.json()["case"]["next_retry_at"] is None


def test_cancellation_cancels_scheduled_retry(client):
    assert signed_request(client, event()).status_code == 200
    cancelled = signed_request(client, event("evt_cancel", "payment_intent.canceled"))
    assert cancelled.json()["case"]["status"] == "cancelled"


def test_invalid_signature_is_rejected_before_json_parsing(client):
    response = client.post(
        "/webhooks/stripe",
        content=b"not-json",
        headers={"Stripe-Signature": "t=1,v1=invalid"},
    )
    assert response.status_code == 400
    assert "signature" in response.json()["detail"]


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"id": "evt", "type": "payment_intent.payment_failed", "created": 1},
        {
            "id": "evt",
            "type": "unknown.event",
            "created": 1,
            "data": {"object": {"id": "pi"}},
        },
    ],
)
def test_malformed_or_unsupported_events_fail_closed(client, payload):
    assert signed_request(client, payload).status_code == 422


def test_decision_endpoint_rejects_unknown_fields(client):
    response = client.post(
        "/v1/decisions/stripe",
        json={
            "decline_code": "insufficient_funds",
            "attempts_completed": 0,
            "occurred_at": "2026-08-09T00:00:00Z",
            "unexpected": True,
        },
    )
    assert response.status_code == 422
