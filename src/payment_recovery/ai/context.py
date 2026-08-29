from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta
from typing import Any

from ..models import CustomerRevenueContext, RevenueEvent

# In-memory store for synthetic / loaded customer contexts
_CUSTOMER_DB: dict[str, CustomerRevenueContext] = {}


def get_or_create_customer_context(
    customer_id: str, event: RevenueEvent | None = None
) -> CustomerRevenueContext:
    """Retrieve existing customer revenue context or create a deterministic context based on customer_id."""
    if customer_id in _CUSTOMER_DB:
        return _CUSTOMER_DB[customer_id]

    # Seed deterministic pseudo-random generator using customer_id
    seed_val = int.from_bytes(customer_id.encode("utf-8")[:4], "big")
    rng = random.Random(seed_val)

    # Determine segment and characteristics
    segments = ["VIP", "Standard", "At-Risk", "New"]
    weights = [0.15, 0.55, 0.20, 0.10]
    segment = rng.choices(segments, weights=weights)[0]

    if segment == "VIP":
        ltv = rng.uniform(50000, 250000)
        success_rate = rng.uniform(0.85, 0.98)
        prev_failures = rng.randint(0, 2)
        prev_recoveries = prev_failures
        total_payments = rng.randint(20, 100)
        tenure_days = rng.randint(180, 730)
    elif segment == "Standard":
        ltv = rng.uniform(10000, 60000)
        success_rate = rng.uniform(0.70, 0.90)
        prev_failures = rng.randint(1, 4)
        prev_recoveries = rng.randint(0, prev_failures)
        total_payments = rng.randint(5, 30)
        tenure_days = rng.randint(60, 365)
    elif segment == "At-Risk":
        ltv = rng.uniform(5000, 30000)
        success_rate = rng.uniform(0.40, 0.68)
        prev_failures = rng.randint(3, 8)
        prev_recoveries = rng.randint(0, 2)
        total_payments = rng.randint(4, 20)
        tenure_days = rng.randint(30, 180)
    else:  # New
        ltv = rng.uniform(1000, 15000)
        success_rate = rng.uniform(0.50, 0.85)
        prev_failures = rng.randint(0, 1)
        prev_recoveries = 0
        total_payments = rng.randint(1, 5)
        tenure_days = rng.randint(1, 45)

    amount = event.amount if event else rng.uniform(1000, 25000)
    days_overdue = rng.randint(0, 15) if (event and event.invoice_id) else 0

    prev_interventions = rng.randint(0, 3)
    response_rate = (
        (prev_recoveries / prev_interventions) if prev_interventions > 0 else rng.uniform(0.3, 0.8)
    )

    context = CustomerRevenueContext(
        customer_id=customer_id,
        name=f"Customer {customer_id[-6:]}",
        email=f"user_{customer_id[-6:]}@example.in",
        ltv=round(ltv, 2),
        historical_success_rate=round(success_rate, 2),
        total_payments_count=total_payments,
        previous_failures_count=prev_failures,
        previous_recoveries_count=prev_recoveries,
        avg_transaction_amount=round(amount, 2),
        subscription_tenure_days=tenure_days,
        days_overdue=days_overdue,
        segment=segment,
        previous_interventions_count=prev_interventions,
        last_intervention_at=datetime.now(UTC) - timedelta(days=rng.randint(2, 30))
        if prev_interventions > 0
        else None,
        response_to_past_interventions_rate=round(response_rate, 2),
    )

    _CUSTOMER_DB[customer_id] = context
    return context


def register_customer_context(context: CustomerRevenueContext) -> None:
    """Register custom or synthetic customer context."""
    _CUSTOMER_DB[context.customer_id] = context
