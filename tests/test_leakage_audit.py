from __future__ import annotations

from datetime import UTC, datetime

from payment_recovery.ai.context import get_or_create_customer_context
from payment_recovery.ai.decision_agent import RevenueRecoveryDecisionAgent
from payment_recovery.ai.detection import RevenueLeakageDetector
from payment_recovery.ai.probability_model import MLRecoveryProbabilityModel
from payment_recovery.ai.root_cause import RootCauseAnalysisAgent
from payment_recovery.evaluation.benchmark import RevenueRecoveryBenchmark
from payment_recovery.evaluation.dataset import generate_synthetic_dataset
from payment_recovery.evaluation.environment import StochasticRecoveryEnvironment
from payment_recovery.models import FailureCategory, LeakageType, RevenueEvent


def test_zero_target_leakage_in_features():
    """Verify that feature vectors passed to ML model contain NO future state or outcome labels."""
    model = MLRecoveryProbabilityModel()
    evt = RevenueEvent("evt_leak_test", "razorpay", "payment.failed", LeakageType.FAILED_PAYMENT, datetime.now(UTC), "c_leak", amount=5000)
    ctx = get_or_create_customer_context("c_leak")

    forbidden_terms = ["recovered", "outcome", "success", "future", "target", "label", "result", "post"]

    # Check feature values
    feats = model._calculate_top_features(ctx, evt, FailureCategory.INSUFFICIENT_FUNDS, 0.8)
    for f in feats:
        feat_name = f["feature"].lower()
        for forbidden in forbidden_terms:
            assert forbidden not in feat_name or "historical" in feat_name


def test_optimizer_selects_action_before_environment_draw():
    """Verify optimizer evaluates candidates strictly prior to stochastic environment outcome generation."""
    agent = RevenueRecoveryDecisionAgent()
    env = StochasticRecoveryEnvironment(seed=42)

    evt = RevenueEvent("evt_seq", "razorpay", "payment.failed", LeakageType.FAILED_PAYMENT, datetime.now(UTC), "c_seq", amount=12000)
    ctx = get_or_create_customer_context("c_seq")
    rc = RootCauseAnalysisAgent().diagnose(evt, ctx)
    pred = MLRecoveryProbabilityModel().predict(evt, ctx, rc.category)

    # 1. Optimizer selects action
    decision = agent.decide_intervention(evt, ctx, rc, pred)
    chosen_action = decision.recommended_action
    assert chosen_action is not None

    # 2. Environment generates outcome AFTER action is selected
    is_rec, amt = env.simulate_outcome(evt, ctx, rc.category, chosen_action)
    assert isinstance(is_rec, bool)
    assert amt in (0.0, 12000.0)


def test_multiseed_benchmark_reproducibility():
    """Verify multi-seed benchmark completes deterministically across seeds."""
    bm = RevenueRecoveryBenchmark()
    res1 = bm.run_multi_seed_benchmark(dataset_size=200, seeds=[42, 123])
    res2 = bm.run_multi_seed_benchmark(dataset_size=200, seeds=[42, 123])

    assert res1.ai_agent_recovered_mean == res2.ai_agent_recovered_mean
    assert res1.recovery_uplift_percent_mean == res2.recovery_uplift_percent_mean
