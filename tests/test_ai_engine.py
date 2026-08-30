from __future__ import annotations

from datetime import UTC, datetime

from payment_recovery.ai.context import get_or_create_customer_context
from payment_recovery.ai.decision_agent import RevenueRecoveryDecisionAgent
from payment_recovery.ai.detection import RevenueLeakageDetector
from payment_recovery.ai.probability_model import MLRecoveryProbabilityModel
from payment_recovery.ai.root_cause import RootCauseAnalysisAgent
from payment_recovery.evaluation.benchmark import RevenueRecoveryBenchmark
from payment_recovery.models import (
    FailureCategory,
    LeakageType,
    RevenueEvent,
)
from payment_recovery.policy.guardrails import DeterministicGuardrailEngine, GuardrailStatus


def test_revenue_leakage_detector():
    detector = RevenueLeakageDetector()
    evt = RevenueEvent(
        event_id="evt_test_01",
        provider="razorpay",
        event_type="order.failed",
        leakage_type=LeakageType.CHECKOUT_ABANDONMENT,
        occurred_at=datetime.now(UTC),
        customer_id="cust_test_1",
        amount=25000.0,
    )

    res = detector.analyze_event(evt)
    assert res["leakage_type"] == LeakageType.CHECKOUT_ABANDONMENT
    assert res["amount_at_risk"] == 25000.0
    assert res["requires_intervention"] is True


def test_root_cause_and_probability_model():
    rc_agent = RootCauseAnalysisAgent()
    prob_model = MLRecoveryProbabilityModel()

    evt = RevenueEvent(
        event_id="evt_test_02",
        provider="razorpay",
        event_type="payment.failed",
        leakage_type=LeakageType.FAILED_PAYMENT,
        occurred_at=datetime.now(UTC),
        customer_id="cust_test_2",
        amount=10000.0,
        failure_code="BAD_REQUEST_ERROR",
        failure_reason="Insufficient balance",
    )

    ctx = get_or_create_customer_context("cust_test_2", evt)
    diagnosis = rc_agent.diagnose(evt, ctx)
    assert diagnosis.category == FailureCategory.INSUFFICIENT_FUNDS

    prediction = prob_model.predict(evt, ctx, diagnosis.category)
    assert 0.0 <= prediction.recovery_probability <= 1.0
    assert prediction.expected_recovery_value == round(10000.0 * prediction.recovery_probability, 2)


def test_guardrails_engine():
    guardrail = DeterministicGuardrailEngine()

    evt = RevenueEvent(
        event_id="evt_test_03",
        provider="razorpay",
        event_type="payment.failed",
        leakage_type=LeakageType.FAILED_PAYMENT,
        occurred_at=datetime.now(UTC),
        customer_id="cust_test_3",
        amount=100000.0,  # > 50,000 threshold
        failure_code="BAD_REQUEST_ERROR",
    )
    ctx = get_or_create_customer_context("cust_test_3", evt)
    rc = RootCauseAnalysisAgent().diagnose(evt, ctx)
    pred = MLRecoveryProbabilityModel().predict(evt, ctx, rc.category)
    dec = RevenueRecoveryDecisionAgent().decide_intervention(evt, ctx, rc, pred)

    result = guardrail.validate(evt, ctx, dec, pred)
    assert result.status == GuardrailStatus.HUMAN_REVIEW


def test_benchmark_evaluation():
    benchmark = RevenueRecoveryBenchmark()
    res = benchmark.run_benchmark(dataset_size=100, seed=42)

    assert res.total_records == 100
    assert res.total_revenue_at_risk > 0
    assert res.ai_recovered_inr >= 0
    assert res.precision_percent >= 0.0
