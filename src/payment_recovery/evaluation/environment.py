from __future__ import annotations

import random

from ..models import (
    CustomerRevenueContext,
    FailureCategory,
    InterventionType,
    LeakageType,
    RevenueEvent,
)


class StochasticRecoveryEnvironment:
    """Independent ground-truth environment simulator modeling real-world payment recovery
    dynamics."""

    def __init__(self, seed: int = 42) -> None:
        self.rng = random.Random(seed)

    def get_ground_truth_payoff(
        self,
        event: RevenueEvent,
        context: CustomerRevenueContext,
        category: FailureCategory,
        action: InterventionType,
    ) -> float:
        """Calculate the TRUE underlying stochastic probability
        P_true(recovered | context, failure, action).

        The AI model NEVER sees this function; it only observes historical features X.
        """
        if action == InterventionType.NO_ACTION:
            return 0.02 if category != FailureCategory.TEMPORARY_PROCESSING else 0.15

        if category == FailureCategory.SECURITY_OR_FRAUD:
            # Security declines almost never recover via automated action
            return 0.01

        if category == FailureCategory.HARD_DECLINE:
            # Hard declines (do_not_honor, blocked account) rarely recover unless card updated
            if action == InterventionType.UPDATE_PAYMENT_METHOD:
                return 0.25 if context.ltv > 20000 else 0.12
            return 0.03

        # Base customer responsiveness from historical success rate & LTV
        base_resp = (
            0.30 + 0.45 * context.historical_success_rate + 0.10 * min(1.0, context.ltv / 100000.0)
        )

        # ---------------------------------------------------------------------
        # 1. FAILED PAYMENTS / SUBSCRIPTIONS (INSUFFICIENT FUNDS)
        # ---------------------------------------------------------------------
        if category == FailureCategory.INSUFFICIENT_FUNDS:
            if action == InterventionType.DELAYED_RETRY:
                # 48h / 120h delay aligns with payday/balance reloading -> High success
                prob = base_resp + 0.25
            elif action == InterventionType.RETRY:
                # Immediate retry fails 80%+ because account hasn't reloaded
                prob = base_resp - 0.25
            elif action in (
                InterventionType.PAYMENT_REMINDER,
                InterventionType.PERSONALIZED_MESSAGE,
            ):
                prob = base_resp + 0.15
            elif action == InterventionType.UPDATE_PAYMENT_METHOD:
                prob = base_resp + 0.10
            else:
                prob = base_resp - 0.10

        # ---------------------------------------------------------------------
        # 2. TEMPORARY PROCESSING / GATEWAY TIMEOUTS
        # ---------------------------------------------------------------------
        elif category == FailureCategory.TEMPORARY_PROCESSING:
            if action in (InterventionType.RETRY, InterventionType.DELAYED_RETRY):
                prob = base_resp + 0.35  # High recovery once gateway recovers
            else:
                prob = base_resp + 0.10

        # ---------------------------------------------------------------------
        # 3. INVALID / EXPIRED PAYMENT METHOD
        # ---------------------------------------------------------------------
        elif category == FailureCategory.INVALID_PAYMENT_METHOD:
            if action == InterventionType.UPDATE_PAYMENT_METHOD:
                prob = base_resp + 0.30  # Customer updating card details works
            elif action in (InterventionType.RETRY, InterventionType.DELAYED_RETRY):
                prob = 0.02  # Retrying an expired card directly fails
            else:
                prob = base_resp * 0.5

        # ---------------------------------------------------------------------
        # 4. CHECKOUT ABANDONMENT
        # ---------------------------------------------------------------------
        elif event.leakage_type == LeakageType.CHECKOUT_ABANDONMENT:
            if action == InterventionType.CHECKOUT_RECOVERY:
                prob = base_resp + 0.32  # 1-click checkout recovery link
            elif action in (
                InterventionType.PAYMENT_REMINDER,
                InterventionType.PERSONALIZED_MESSAGE,
            ):
                prob = base_resp + 0.18
            elif action in (InterventionType.RETRY, InterventionType.DELAYED_RETRY):
                prob = 0.0  # Retrying an unsubmitted checkout fails
            else:
                prob = base_resp * 0.4

        # ---------------------------------------------------------------------
        # 5. OVERDUE RECEIVABLES / INVOICES
        # ---------------------------------------------------------------------
        elif event.leakage_type == LeakageType.OVERDUE_RECEIVABLE:
            if action == InterventionType.INVOICE_REMINDER:
                prob = base_resp + 0.28  # Invoice reminder with 1-click link
            elif action == InterventionType.PERSONALIZED_MESSAGE:
                prob = base_resp + 0.20
            elif action in (InterventionType.RETRY, InterventionType.DELAYED_RETRY):
                prob = 0.0  # Invoices cannot be retried via automated card charge directly
            else:
                prob = base_resp * 0.3

        else:
            prob = base_resp

        # Customer fatigue penalty: repeated interventions reduce response probability
        if context.previous_interventions_count > 0:
            prob *= 0.85**context.previous_interventions_count

        # Add environmental stochastic noise (+/- 5%)
        noise = self.rng.uniform(-0.05, 0.05)
        final_prob = max(0.01, min(0.95, prob + noise))

        return round(final_prob, 4)

    def simulate_outcome(
        self,
        event: RevenueEvent,
        context: CustomerRevenueContext,
        category: FailureCategory,
        action: InterventionType,
    ) -> tuple[bool, float]:
        """Draw a Bernoulli random variable representing the actual executed outcome.

        Returns (is_recovered: bool, actual_amount_recovered: float).
        """
        p_true = self.get_ground_truth_payoff(event, context, category, action)
        is_recovered = self.rng.random() < p_true
        recovered_amount = event.amount if is_recovered else 0.0
        return is_recovered, recovered_amount
