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


def test_dashboard_serves_full_frontend_ui(client):
    """Ensure root and dashboard endpoints return the complete fintech UI."""
    for path in ["/", "/dashboard"]:
        response = client.get(path)
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        # Validate that it is the complete rich dashboard (>50KB) and not a plain heading
        assert len(response.text) > 50000
        assert "Razorpay AI Revenue Recovery Agent" in response.text
        assert "Command Center" in response.text
        assert "Plus Jakarta Sans" in response.text
        assert "app-layout" in response.text
        assert "btn-simulate" in response.text
        assert "btn-benchmark" in response.text
        assert "chartComparison" in response.text
        assert "review-queue-container" in response.text
        assert "audit-container" in response.text
        assert "status-container" in response.text


def test_static_and_ui_mounts(client):
    """Ensure static / ui mounts serve the index.html and assets."""
    for path in ["/static/index.html", "/ui/index.html"]:
        response = client.get(path)
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        assert len(response.text) > 50000


def test_frontend_api_endpoints(client):
    """Verify all backend endpoints used by the dashboard UI."""
    # Health check
    res_health = client.get("/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "ok"

    # System status
    res_status = client.get("/system/status")
    assert res_status.status_code == 200
    assert res_status.json()["backend"] == "operational"

    # Metrics
    res_metrics = client.get("/recovery/metrics")
    assert res_metrics.status_code == 200
    assert "revenue_at_risk" in res_metrics.json()

    # Cases
    res_cases = client.get("/recovery/cases")
    assert res_cases.status_code == 200
    assert "cases" in res_cases.json()

    # Review queue
    res_queue = client.get("/recovery/review-queue")
    assert res_queue.status_code == 200
    assert "queue" in res_queue.json()

    # Audit logs
    res_audit = client.get("/audit/logs")
    assert res_audit.status_code == 200
    assert "logs" in res_audit.json()

    # Benchmark results
    res_bm = client.get("/benchmark/results")
    assert res_bm.status_code == 200

    # Simulation trigger
    res_sim = client.post("/demo/simulate")
    assert res_sim.status_code == 200
    assert res_sim.json()["status"] == "success"

