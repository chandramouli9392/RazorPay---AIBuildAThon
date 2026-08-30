from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta

from ..models import CustomerRevenueContext, FailureCategory, LeakageType, RevenueEvent


def generate_synthetic_dataset(
    count: int = 5000, seed: int = 42
) -> list[tuple[RevenueEvent, CustomerRevenueContext]]:
    """Generate reproducible synthetic dataset of pre-intervention revenue events
    and customer contexts.

    Features generated are strictly pre-intervention and contain NO future states
    or target labels.
    """
    rng = random.Random(seed)
    dataset: list[tuple[RevenueEvent, CustomerRevenueContext]] = []

    leakage_weights = [0.45, 0.30, 0.15, 0.10]
    leakage_types = [
        LeakageType.FAILED_PAYMENT,
        LeakageType.FAILED_SUBSCRIPTION,
        LeakageType.CHECKOUT_ABANDONMENT,
        LeakageType.OVERDUE_RECEIVABLE,
    ]

    failure_reasons = {
        FailureCategory.INSUFFICIENT_FUNDS: (
            "BAD_REQUEST_ERROR",
            "Insufficient funds in customer account",
        ),
        FailureCategory.TEMPORARY_PROCESSING: (
            "GATEWAY_ERROR",
            "Temporary bank network timeout",
        ),
        FailureCategory.INVALID_PAYMENT_METHOD: (
            "INVALID_CARD",
            "Expired or invalid card details",
        ),
        FailureCategory.AUTHENTICATION_REQUIRED: (
            "AUTH_FAILED",
            "Customer 3DS authentication required",
        ),
        FailureCategory.SECURITY_OR_FRAUD: (
            "RISK_CHECK_FAILED",
            "Flagged by security risk engine",
        ),
        FailureCategory.HARD_DECLINE: ("DO_NOT_HONOR", "Issuer hard decline"),
    }
    failure_categories = list(failure_reasons.keys())
    cat_weights = [0.40, 0.25, 0.15, 0.10, 0.05, 0.05]

    for i in range(1, count + 1):
        l_type = rng.choices(leakage_types, weights=leakage_weights)[0]
        cust_id = f"cust_synth_{rng.randint(1000, 9999)}"

        if l_type == LeakageType.FAILED_SUBSCRIPTION:
            amount = float(rng.choice([499, 999, 1999, 4999, 9999, 14999]))
        elif l_type == LeakageType.CHECKOUT_ABANDONMENT:
            amount = float(rng.choice([1499, 2999, 5999, 12999, 25000, 45000]))
        elif l_type == LeakageType.OVERDUE_RECEIVABLE:
            amount = float(rng.choice([10000, 25000, 50000, 100000, 250000]))
        else:
            amount = float(rng.choice([500, 1200, 2500, 5000, 10000, 20000, 60000]))

        f_cat = rng.choices(failure_categories, weights=cat_weights)[0]
        f_code, f_desc = failure_reasons[f_cat]

        evt_id = f"evt_synth_{i:05d}"
        occurred_at = datetime.now(UTC) - timedelta(hours=rng.randint(1, 720))

        event = RevenueEvent(
            event_id=evt_id,
            provider="razorpay",
            event_type=(
                "payment.failed"
                if l_type == LeakageType.FAILED_PAYMENT
                else f"{l_type.value}.failed"
            ),
            leakage_type=l_type,
            occurred_at=occurred_at,
            customer_id=cust_id,
            payment_id=f"pay_{evt_id[:10]}" if l_type != LeakageType.CHECKOUT_ABANDONMENT else None,
            order_id=f"order_{evt_id[:10]}",
            subscription_id=(
                f"sub_{evt_id[:10]}" if l_type == LeakageType.FAILED_SUBSCRIPTION else None
            ),
            invoice_id=(f"inv_{evt_id[:10]}" if l_type == LeakageType.OVERDUE_RECEIVABLE else None),
            amount=amount,
            currency="INR",
            status="failed" if l_type != LeakageType.OVERDUE_RECEIVABLE else "overdue",
            failure_code=f_code,
            failure_reason=f_desc,
            metadata={"synthetic": True},
        )

        ltv = amount * rng.uniform(2, 20)
        success_rate = rng.uniform(0.35, 0.95)
        prev_failures = rng.randint(0, 5)
        prev_recoveries = rng.randint(0, prev_failures)
        tenure = rng.randint(10, 700)
        days_overdue = rng.randint(1, 30) if l_type == LeakageType.OVERDUE_RECEIVABLE else 0

        segment = (
            "VIP"
            if ltv > 50000
            else "Standard"
            if ltv > 15000
            else "At-Risk"
            if success_rate < 0.6
            else "New"
        )

        context = CustomerRevenueContext(
            customer_id=cust_id,
            name=f"Synthetic Customer {i}",
            email=f"synth_{i}@example.in",
            ltv=round(ltv, 2),
            historical_success_rate=round(success_rate, 2),
            total_payments_count=rng.randint(2, 50),
            previous_failures_count=prev_failures,
            previous_recoveries_count=prev_recoveries,
            avg_transaction_amount=round(amount, 2),
            subscription_tenure_days=tenure,
            days_overdue=days_overdue,
            segment=segment,
            previous_interventions_count=rng.randint(0, 2),
            response_to_past_interventions_rate=round(rng.uniform(0.2, 0.8), 2),
        )

        dataset.append((event, context))

    return dataset
