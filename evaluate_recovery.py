#!/usr/bin/env python3
"""
Razorpay AI Revenue Recovery Agent — Audit-Proof Multi-Seed Benchmark Script

Run this script to reproduce the leak-free, multi-seed comparative benchmark across
Naive Fixed Retry, Standard Rule-Based Policy, and the Razorpay AI Revenue Recovery Agent.

Usage:
    python evaluate_recovery.py [--records 5000] [--multiseed]
"""

from __future__ import annotations

import argparse
import os
import sys

# Reconfigure stdout to UTF-8 for Windows console support
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Ensure src is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "src")))

from payment_recovery.evaluation.benchmark import RevenueRecoveryBenchmark


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Razorpay AI Revenue Recovery Agent Multi-Seed Benchmark Evaluator"
    )
    parser.add_argument(
        "--records",
        type=int,
        default=5000,
        help="Number of synthetic revenue records (default: 5000)",
    )
    parser.add_argument(
        "--multiseed",
        action="store_true",
        help="Run multi-seed evaluation across seeds [42, 123, 456, 789, 2026]",
    )
    args = parser.parse_args()

    print("\nRunning Razorpay AI Revenue Recovery Audit-Proof Benchmark...", flush=True)
    benchmark = RevenueRecoveryBenchmark()

    if args.multiseed:
        seeds = [42, 123, 456, 789, 2026]
        res = benchmark.run_multi_seed_benchmark(dataset_size=args.records, seeds=seeds)

        print("\n" + "=" * 85, flush=True)
        print(
            "      RAZORPAY AI REVENUE RECOVERY AGENT — MULTI-SEED BENCHMARK EVALUATION", flush=True
        )
        print("=" * 85, flush=True)
        print(
            f"  Benchmark Records Analyzed:  {res.total_records:,} per seed (5 Random Seeds: {seeds})",
            flush=True,
        )
        print(
            "  Evaluation Methodology:      Leak-Free Stochastic Environment Engine (No Oracle Access)",
            flush=True,
        )
        print("-" * 85, flush=True)
        print("  THREE-TIER STRATEGY COMPARISON (MEAN ± STD DEV):", flush=True)
        print(
            f"    Total Revenue At Risk:             INR {res.total_revenue_at_risk:,.2f}",
            flush=True,
        )
        print(
            f"    Baseline 1 (Naive Fixed Retry):    INR {res.naive_baseline_recovered_mean:,.2f}  ({(res.naive_baseline_recovered_mean / res.total_revenue_at_risk) * 100:.1f}%)",
            flush=True,
        )
        print(
            f"    Baseline 2 (Standard Rule Policy): INR {res.rule_baseline_recovered_mean:,.2f}  ({(res.rule_baseline_recovered_mean / res.total_revenue_at_risk) * 100:.1f}%)",
            flush=True,
        )
        print(
            f"    AI Revenue Recovery Agent:         INR {res.ai_agent_recovered_mean:,.2f} ± {res.ai_agent_recovered_std:,.2f}  ({(res.ai_agent_recovered_mean / res.total_revenue_at_risk) * 100:.1f}%)",
            flush=True,
        )
        print("-" * 85, flush=True)
        print("  INCREMENTAL VALUE CREATED BY AI AGENT:", flush=True)
        print(
            f"    Incremental Revenue vs Rule Base:  INR {res.incremental_revenue_mean:,.2f}",
            flush=True,
        )
        print(
            f"    AI Recovery Uplift vs Rule Base:   +{res.recovery_uplift_percent_mean:.1f}% Net Uplift",
            flush=True,
        )
        print("-" * 85, flush=True)
        print("  MACHINE LEARNING ACCURACY & SAFETY METRICS:", flush=True)
        print(f"    Intervention Precision:            {res.precision_mean:.1f}%", flush=True)
        print(f"    Intervention Recall:               {res.recall_mean:.1f}%", flush=True)
        print(f"    F1 Score:                          {res.f1_score_mean:.1f}%", flush=True)
        print(f"    ROC-AUC Score:                     {res.roc_auc_score:.3f}", flush=True)
        print(f"    Guardrail Policy Blocks (Mean):    {res.guardrail_blocks_mean:,}", flush=True)
        print(f"    Human Escalations Flagged (Mean):  {res.human_escalations_mean:,}", flush=True)
        print("=" * 85 + "\n", flush=True)

    else:
        tot_risk, naive_rec, rule_rec, metrics = benchmark.run_single_seed_benchmark(
            dataset_size=args.records, seed=42
        )

        print("\n" + "=" * 85, flush=True)
        print(
            "      RAZORPAY AI REVENUE RECOVERY AGENT — BENCHMARK EVALUATION (SEED 42)", flush=True
        )
        print("=" * 85, flush=True)
        print(f"  Benchmark Records Analyzed:  {args.records:,} (Seed: 42)", flush=True)
        print("  Evaluation Methodology:      Leak-Free Stochastic Environment Engine", flush=True)
        print("-" * 85, flush=True)
        print("  THREE-TIER STRATEGY COMPARISON:", flush=True)
        print(f"    Total Revenue At Risk:             INR {tot_risk:,.2f}", flush=True)
        print(
            f"    Baseline 1 (Naive Fixed Retry):    INR {naive_rec:,.2f}  ({(naive_rec / tot_risk) * 100:.1f}%)",
            flush=True,
        )
        print(
            f"    Baseline 2 (Standard Rule Policy): INR {rule_rec:,.2f}  ({(rule_rec / tot_risk) * 100:.1f}%)",
            flush=True,
        )
        print(
            f"    AI Revenue Recovery Agent:         INR {metrics.recovered_inr:,.2f}  ({metrics.recovery_rate_percent:.1f}%)",
            flush=True,
        )
        print("-" * 85, flush=True)
        print("  INCREMENTAL VALUE CREATED BY AI AGENT:", flush=True)
        print(
            f"    Incremental Revenue vs Rule Base:  INR {metrics.incremental_vs_rule_inr:,.2f}",
            flush=True,
        )
        print(
            f"    AI Recovery Uplift vs Rule Base:   +{metrics.uplift_vs_rule_percent:.1f}% Net Uplift",
            flush=True,
        )
        print("-" * 85, flush=True)
        print("  MACHINE LEARNING ACCURACY & SAFETY METRICS:", flush=True)
        print(
            f"    Intervention Precision:            {metrics.precision_percent:.1f}%", flush=True
        )
        print(f"    Intervention Recall:               {metrics.recall_percent:.1f}%", flush=True)
        print(f"    F1 Score:                          {metrics.f1_score_percent:.1f}%", flush=True)
        print(
            f"    Unnecessary Retries / Fatigue:     {metrics.unnecessary_interventions_percent:.1f}%",
            flush=True,
        )
        print(
            f"    Guardrail Policy Blocks:           {metrics.guardrail_blocks_count:,}", flush=True
        )
        print(
            f"    Human Escalations Flagged:         {metrics.human_escalations_count:,}",
            flush=True,
        )
        print("=" * 85 + "\n", flush=True)


if __name__ == "__main__":
    main()
