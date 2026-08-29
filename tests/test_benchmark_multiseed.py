from __future__ import annotations

from payment_recovery.evaluation.benchmark import RevenueRecoveryBenchmark


def test_multiseed_benchmark_execution_and_ordering():
    """Verify multi-seed benchmark returns valid stats and preserves AI > Rule > Naive ordering."""
    benchmark = RevenueRecoveryBenchmark()
    seeds = [42, 123, 456, 789, 2026]
    res = benchmark.run_multi_seed_benchmark(dataset_size=500, seeds=seeds)

    # 1. Seeds & dataset size checks
    assert res.seeds_evaluated == seeds
    assert res.total_records == 500
    assert res.total_revenue_at_risk > 0.0

    # 2. Strict Performance Hierarchy: AI Agent > Rule Baseline > Naive Baseline
    assert res.ai_agent_recovered_mean > res.rule_baseline_recovered_mean
    assert res.rule_baseline_recovered_mean > res.naive_baseline_recovered_mean

    # 3. Financial Impact metrics
    assert res.incremental_revenue_mean > 0.0
    assert res.recovery_uplift_percent_mean > 50.0  # Net uplift > 50%

    # 4. Statistical rigor check (std dev should be calculated and non-negative)
    assert res.ai_agent_recovered_std >= 0.0

    # 5. ML Accuracy metrics sanity
    assert 0.0 <= res.precision_mean <= 100.0
    assert 0.0 <= res.recall_mean <= 100.0
    assert 0.0 <= res.f1_score_mean <= 100.0
    assert 0.0 <= res.roc_auc_score <= 1.0


def test_single_seed_benchmark_reproducibility():
    """Verify single seed execution is 100% deterministic."""
    bm = RevenueRecoveryBenchmark()
    tot1, naive1, rule1, metrics1 = bm.run_single_seed_benchmark(dataset_size=300, seed=42)
    tot2, naive2, rule2, metrics2 = bm.run_single_seed_benchmark(dataset_size=300, seed=42)

    assert tot1 == tot2
    assert naive1 == naive2
    assert rule1 == rule2
    assert metrics1.recovered_inr == metrics2.recovered_inr
    assert metrics1.precision_percent == metrics2.precision_percent
    assert metrics1.guardrail_blocks_count == metrics2.guardrail_blocks_count
