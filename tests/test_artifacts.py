import json
import re
from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_all_n8n_workflows_are_valid_inactive_json_without_embedded_secrets():
    workflows = sorted((ROOT / "n8n-workflows").glob("*.json"))
    assert len(workflows) == 5
    for path in workflows:
        document = json.loads(path.read_text())
        assert document["active"] is False
        assert document["nodes"]
        names = {node["name"] for node in document["nodes"]}
        assert len(names) == len(document["nodes"])
        for node in document["nodes"]:
            assert {"id", "name", "type", "typeVersion", "position", "parameters"} <= node.keys()
            for credential in node.get("credentials", {}).values():
                assert set(credential) == {"name"}
        assert set(document.get("connections", {})) <= names
        for sources in document.get("connections", {}).values():
            for output in sources["main"]:
                for connection in output:
                    assert connection["node"] in names
        text = path.read_text()
        assert not re.search(r"(?:sk|whsec)_(?:test|live)_[A-Za-z0-9]+", text)
        assert "service_role" not in text


def test_n8n_does_not_reimplement_provider_classification_or_signature_logic():
    text = "\n".join(path.read_text() for path in (ROOT / "n8n-workflows").glob("*.json"))
    assert "do_not_honor" not in text
    assert "fraudulent" not in text
    assert "createHmac" not in text
    assert "STRIPE_WEBHOOK_SECRET" not in text


def test_retry_worker_has_atomic_claim_provider_recheck_and_idempotency_key():
    text = (ROOT / "n8n-workflows/4-retry-scheduler.json").read_text()
    assert "claim_due_retries" in text
    assert "Recheck Provider State" in text
    assert "Idempotency-Key" in text


def test_templates_are_html_and_use_runtime_placeholders():
    templates = sorted((ROOT / "email-templates").glob("*.html"))
    assert len(templates) == 3
    for template in templates:
        text = template.read_text()
        assert text.startswith("<!doctype html>")
        assert "{{" in text and "}}" in text
        assert "example.com" not in text
        assert "[support email]" not in text


def test_security_template_is_explicitly_internal_and_non_disclosing():
    text = (ROOT / "email-templates/fraud-alert.html").read_text().lower()
    assert "internal" in text
    assert "do not automatically retry" in text
    assert "do not" in text and "disclose" in text


def test_sample_data_uses_reserved_synthetic_domains_and_no_outcome_claims():
    text = (ROOT / "database/sample-data.sql").read_text().lower()
    assert "example.invalid" in text
    assert "recovery rate" in text  # present only in the explicit no-claim warning
    assert "$" not in text


def test_sample_webhooks_are_structured_synthetic_events():
    events = json.loads((ROOT / "tests/test-data/sample-webhooks.json").read_text())
    assert len(events) == 3
    assert len({event["id"] for event in events}) == len(events)
    for event in events:
        assert event["type"] == "payment_intent.payment_failed"
        email = event["data"]["object"].get("receipt_email")
        assert email is None or email.endswith("@example.invalid")
