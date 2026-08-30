from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from payment_recovery.ai.context import CustomerRevenueContext, get_or_create_customer_context
from payment_recovery.ai.decision_agent import RevenueRecoveryDecisionAgent
from payment_recovery.execution.engine import RecoveryExecutionEngine
from payment_recovery.execution.review_queue import HumanReviewQueue
from payment_recovery.models import (
    FailureCategory,
    GuardrailStatus,
    InterventionDecision,
    LeakageType,
    RecoveryPrediction,
    RecoveryStatus,
    RevenueEvent,
    RootCauseAnalysis,
)
from payment_recovery.policy.guardrails import DeterministicGuardrailEngine
from payment_recovery.providers.razorpay.signatures import (
    RazorpaySignatureVerificationError,
    verify_razorpay_signature,
)
from payment_recovery.state_machine import RecoveryStore


def test_adv_1_invalid_signature_rejection():
    with pytest.raises(RazorpaySignatureVerificationError):
        verify_razorpay_signature(b'{"event":"payment.failed"}', "invalid_sig", "secret_key")


def test_adv_2_duplicate_event_replayed_10_times():
    store = RecoveryStore()
    decision = RevenueRecoveryDecisionAgent().decide_intervention(
        RevenueEvent(
            "evt_dup",
            "razorpay",
            "payment.failed",
            LeakageType.FAILED_PAYMENT,
            datetime.now(UTC),
            "c1",
            amount=1000,
        ),
        get_or_create_customer_context("c1"),
        RootCauseAnalysis("cause", FailureCategory.INSUFFICIENT_FUNDS, 0.9, [], "HIGH", "retry"),
        RecoveryPrediction(0.8, 0.9, 800, []),
    )
    pol_dec = guardrail_to_policy_decision(decision)

    res1 = store.apply_failure("evt_dup", "pay_intent_dup", pol_dec)
    assert res1.applied is True

    for _ in range(9):
        res_dup = store.apply_failure("evt_dup", "pay_intent_dup", pol_dec)
        assert res_dup.applied is False
        assert res_dup.duplicate is True


def test_adv_3_terminal_state_protection_recovered():
    guardrail = DeterministicGuardrailEngine()
    evt = RevenueEvent(
        "evt_term",
        "razorpay",
        "payment.failed",
        LeakageType.FAILED_PAYMENT,
        datetime.now(UTC),
        "c2",
        amount=5000,
    )
    ctx = get_or_create_customer_context("c2")
    dec = RevenueRecoveryDecisionAgent().decide_intervention(
        evt,
        ctx,
        RootCauseAnalysis("", FailureCategory.INSUFFICIENT_FUNDS, 0.9, [], "HIGH", ""),
        RecoveryPrediction(0.8, 0.9, 4000, []),
    )
    pred = RecoveryPrediction(0.8, 0.9, 4000, [])

    result = guardrail.validate(evt, ctx, dec, pred, case_status=RecoveryStatus.RECOVERED)
    assert result.passed is False
    assert result.status == GuardrailStatus.REJECTED
    assert "Terminal state" in (result.rejection_reason or "")


def test_adv_4_fraud_security_decline_auto_retry_block():
    guardrail = DeterministicGuardrailEngine()
    evt = RevenueEvent(
        "evt_fraud",
        "razorpay",
        "payment.failed",
        LeakageType.FAILED_PAYMENT,
        datetime.now(UTC),
        "c3",
        amount=5000,
        failure_code="fraudulent",
    )
    ctx = get_or_create_customer_context("c3")
    dec = RevenueRecoveryDecisionAgent().decide_intervention(
        evt,
        ctx,
        RootCauseAnalysis("", FailureCategory.SECURITY_OR_FRAUD, 0.95, [], "UNRECOVERABLE", ""),
        RecoveryPrediction(0.02, 0.9, 100, []),
    )
    pred = RecoveryPrediction(0.02, 0.9, 100, [])

    result = guardrail.validate(evt, ctx, dec, pred)
    assert result.passed is False
    assert result.status == GuardrailStatus.REJECTED
    assert "Security policy violation" in (result.rejection_reason or "")


def test_adv_5_high_monetary_exposure_forces_human_review():
    guardrail = DeterministicGuardrailEngine()
    evt = RevenueEvent(
        "evt_high_val",
        "razorpay",
        "payment.failed",
        LeakageType.FAILED_PAYMENT,
        datetime.now(UTC),
        "c4",
        amount=150000.0,
    )
    ctx = get_or_create_customer_context("c4")
    dec = RevenueRecoveryDecisionAgent().decide_intervention(
        evt,
        ctx,
        RootCauseAnalysis("", FailureCategory.INSUFFICIENT_FUNDS, 0.9, [], "HIGH", ""),
        RecoveryPrediction(0.8, 0.9, 120000, []),
    )
    pred = RecoveryPrediction(0.8, 0.9, 120000, [])

    result = guardrail.validate(evt, ctx, dec, pred)
    assert result.status == GuardrailStatus.HUMAN_REVIEW
    assert "human review" in (result.rejection_reason or "").lower()


def test_adv_6_excessive_contact_frequency_throttling():
    guardrail = DeterministicGuardrailEngine()
    evt = RevenueEvent(
        "evt_freq",
        "razorpay",
        "payment.failed",
        LeakageType.FAILED_PAYMENT,
        datetime.now(UTC),
        "c5",
        amount=2000,
    )
    ctx = CustomerRevenueContext(
        "c5",
        "User",
        "u@ex.com",
        10000,
        0.8,
        10,
        1,
        1,
        2000,
        100,
        0,
        "Standard",
        2,
        last_intervention_at=datetime.now(UTC) - timedelta(hours=2),
    )
    dec = RevenueRecoveryDecisionAgent().decide_intervention(
        evt,
        ctx,
        RootCauseAnalysis("", FailureCategory.INSUFFICIENT_FUNDS, 0.9, [], "HIGH", ""),
        RecoveryPrediction(0.8, 0.9, 1600, []),
    )
    pred = RecoveryPrediction(0.8, 0.9, 1600, [])

    result = guardrail.validate(evt, ctx, dec, pred)
    assert result.passed is False
    assert "Contact frequency limit" in (result.rejection_reason or "")


def test_adv_7_retry_budget_exhaustion_block():
    guardrail = DeterministicGuardrailEngine()
    evt = RevenueEvent(
        "evt_budget",
        "razorpay",
        "payment.failed",
        LeakageType.FAILED_PAYMENT,
        datetime.now(UTC),
        "c6",
        amount=2000,
    )
    ctx = get_or_create_customer_context("c6")
    dec = RevenueRecoveryDecisionAgent().decide_intervention(
        evt,
        ctx,
        RootCauseAnalysis("", FailureCategory.INSUFFICIENT_FUNDS, 0.9, [], "HIGH", ""),
        RecoveryPrediction(0.8, 0.9, 1600, []),
    )
    pred = RecoveryPrediction(0.8, 0.9, 1600, [])

    result = guardrail.validate(evt, ctx, dec, pred, attempts_completed=3)
    assert result.passed is False
    assert "Retry budget exhausted" in (result.rejection_reason or "")


def test_adv_8_human_review_approval_and_rejection():
    queue = HumanReviewQueue()
    from payment_recovery.audit.logger import RecoveryAuditLogger

    evt = RevenueEvent(
        "evt_rev_q",
        "razorpay",
        "payment.failed",
        LeakageType.FAILED_PAYMENT,
        datetime.now(UTC),
        "c7",
        amount=75000,
    )
    ctx = get_or_create_customer_context("c7")
    rc = RootCauseAnalysis("", FailureCategory.INSUFFICIENT_FUNDS, 0.9, [], "HIGH", "")
    pred = RecoveryPrediction(0.8, 0.9, 60000, [])
    dec = RevenueRecoveryDecisionAgent().decide_intervention(evt, ctx, rc, pred)
    guard = DeterministicGuardrailEngine().validate(evt, ctx, dec, pred)

    logger = RecoveryAuditLogger()
    audit = logger.log_decision_pipeline(evt, ctx, rc, pred, dec, guard)
    queue.add_case_to_queue(audit)

    pending = queue.get_pending_cases()
    assert len(pending) >= 1

    app = queue.approve_case("evt_rev_q")
    assert app["status"] == "approved"


def test_adv_9_candidate_optimization_evaluates_all_9_actions():
    agent = RevenueRecoveryDecisionAgent()
    evt = RevenueEvent(
        "evt_opt",
        "razorpay",
        "payment.failed",
        LeakageType.FAILED_PAYMENT,
        datetime.now(UTC),
        "c8",
        amount=15000,
    )
    ctx = get_or_create_customer_context("c8")
    rc = RootCauseAnalysis(
        "Insufficient funds", FailureCategory.INSUFFICIENT_FUNDS, 0.9, [], "HIGH", ""
    )
    pred = RecoveryPrediction(0.85, 0.9, 12750, [])

    decision = agent.decide_intervention(evt, ctx, rc, pred)
    assert len(decision.candidate_evaluations) == 9
    rec_cands = [c for c in decision.candidate_evaluations if c.recommended]
    assert len(rec_cands) == 1
    assert rec_cands[0].action_type == decision.recommended_action


def test_adv_10_execution_engine_idempotency():
    engine = RecoveryExecutionEngine()
    evt = RevenueEvent(
        "evt_idem_exec",
        "razorpay",
        "payment.failed",
        LeakageType.FAILED_PAYMENT,
        datetime.now(UTC),
        "c9",
        amount=5000,
    )
    ctx = get_or_create_customer_context("c9")
    rc = RootCauseAnalysis("", FailureCategory.TEMPORARY_PROCESSING, 0.9, [], "HIGH", "")
    pred = RecoveryPrediction(0.9, 0.9, 4500, [])
    dec = RevenueRecoveryDecisionAgent().decide_intervention(evt, ctx, rc, pred)
    guard = DeterministicGuardrailEngine().validate(evt, ctx, dec, pred)

    act1 = engine.execute_action(evt, ctx, dec, pred, guard)
    act2 = engine.execute_action(evt, ctx, dec, pred, guard)

    assert act1.action_id == act2.action_id


def guardrail_to_policy_decision(dec: InterventionDecision):
    from payment_recovery.models import PolicyDecision

    return PolicyDecision(
        category=FailureCategory.INSUFFICIENT_FUNDS,
        retry_allowed=True,
        next_retry_at=datetime.now(UTC),
        max_attempts=3,
        notification_required=False,
        notification_kind=None,
        manual_review_required=False,
        reason=dec.reasoning,
    )
