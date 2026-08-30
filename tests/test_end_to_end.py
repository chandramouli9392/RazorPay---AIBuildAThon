from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime

from payment_recovery.ai.context import get_or_create_customer_context
from payment_recovery.ai.decision_agent import RevenueRecoveryDecisionAgent
from payment_recovery.ai.detection import RevenueLeakageDetector
from payment_recovery.ai.probability_model import MLRecoveryProbabilityModel
from payment_recovery.ai.root_cause import RootCauseAnalysisAgent
from payment_recovery.audit.logger import RecoveryAuditLogger
from payment_recovery.execution.engine import RecoveryExecutionEngine
from payment_recovery.models import GuardrailStatus, InterventionType, LeakageType
from payment_recovery.policy.guardrails import DeterministicGuardrailEngine
from payment_recovery.providers.razorpay.adapter import RazorpayProviderAdapter


def test_full_end_to_end_revenue_recovery_pipeline():
    """Verify entire pipeline from webhook signature to audit log & execution outcome."""
    # 1. Ingest Razorpay Webhook
    secret = "whsec_test_secret_123"
    raw_payload = {
        "id": "evt_e2e_test_99",
        "event": "payment.failed",
        "created_at": int(datetime.now(UTC).timestamp()),
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_e2e_99",
                    "amount": 1000000,  # ₹10,000 in paise
                    "currency": "INR",
                    "status": "failed",
                    "customer_id": "cust_e2e_99",
                    "error_code": "BAD_REQUEST_ERROR",
                    "error_description": "Insufficient funds in customer bank account",
                }
            }
        },
    }
    raw_body = str(raw_payload).replace("'", '"').encode("utf-8")
    sig = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()

    adapter = RazorpayProviderAdapter()
    assert adapter.verify_webhook_signature(raw_body, sig, secret) is True

    # 2. Event Normalization
    event = adapter.normalize_event(raw_payload)
    assert event.event_id == "evt_e2e_test_99"
    assert event.leakage_type == LeakageType.FAILED_PAYMENT
    assert event.amount == 10000.0

    # 3. Leakage Detection
    detector = RevenueLeakageDetector()
    leakage_assessment = detector.analyze_event(event)
    assert leakage_assessment["requires_intervention"] is True

    # 4. Context Enrichment
    context = get_or_create_customer_context(event.customer_id, event)
    assert context.customer_id == "cust_e2e_99"

    # 5. Root Cause AI Analysis
    rc_agent = RootCauseAnalysisAgent()
    root_cause = rc_agent.diagnose(event, context)
    assert root_cause.confidence > 0.8

    # 6. ML Recovery Probability
    prob_model = MLRecoveryProbabilityModel()
    prediction = prob_model.predict(event, context, root_cause.category)
    assert 0.0 <= prediction.recovery_probability <= 1.0

    # 7. Candidate Intervention Optimization
    decision_agent = RevenueRecoveryDecisionAgent()
    decision = decision_agent.decide_intervention(event, context, root_cause, prediction)
    assert decision.recommended_action != InterventionType.NO_ACTION
    assert len(decision.candidate_evaluations) == 9  # All 9 candidates evaluated!

    # 8. Deterministic Guardrail Validation
    guardrail_engine = DeterministicGuardrailEngine()
    guardrail = guardrail_engine.validate(event, context, decision, prediction)
    assert guardrail.status in (GuardrailStatus.APPROVED, GuardrailStatus.HUMAN_REVIEW)

    # 9. Execution
    execution_engine = RecoveryExecutionEngine(adapter)
    action = execution_engine.execute_action(event, context, decision, prediction, guardrail)
    assert action.status in ("executed", "simulated", "blocked_by_guardrail")

    # 10. Audit Logging & Human Review Queue
    logger = RecoveryAuditLogger()
    audit = logger.log_decision_pipeline(
        event, context, root_cause, prediction, decision, guardrail, action
    )
    assert audit.audit_id is not None
    assert audit.amount_at_risk == 10000.0
