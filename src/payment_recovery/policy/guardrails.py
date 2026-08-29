from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from ..models import (
    CustomerRevenueContext,
    FailureCategory,
    GuardrailResult,
    GuardrailStatus,
    InterventionDecision,
    InterventionType,
    RecoveryPrediction,
    RecoveryStatus,
    RevenueEvent,
)


class DeterministicGuardrailEngine:
    """Mandatory safety gatekeeper enforcing policy boundaries on AI interventions."""

    MAX_RETRY_COUNT: int = 3
    MAX_AUTO_EXPOSURE_INR: float = 50000.0
    MIN_CONFIDENCE_THRESHOLD: float = 0.15
    MIN_INTERVENTION_INTERVAL_HOURS: int = 12

    ALLOWED_ACTIONS: set[InterventionType] = {
        InterventionType.RETRY,
        InterventionType.DELAYED_RETRY,
        InterventionType.UPDATE_PAYMENT_METHOD,
        InterventionType.PAYMENT_REMINDER,
        InterventionType.PERSONALIZED_MESSAGE,
        InterventionType.CHECKOUT_RECOVERY,
        InterventionType.INVOICE_REMINDER,
        InterventionType.HUMAN_ESCALATION,
        InterventionType.NO_ACTION,
    }

    def validate(
        self,
        event: RevenueEvent,
        context: CustomerRevenueContext,
        decision: InterventionDecision,
        prediction: RecoveryPrediction,
        case_status: RecoveryStatus | None = None,
        attempts_completed: int = 0,
    ) -> GuardrailResult:
        rules_evaluated: list[str] = []

        # Rule 1: Terminal State Protection
        rules_evaluated.append("terminal_state_check")
        if case_status in (RecoveryStatus.RECOVERED, RecoveryStatus.CANCELLED, RecoveryStatus.EXHAUSTED):
            return GuardrailResult(
                passed=False,
                status=GuardrailStatus.REJECTED,
                rejection_reason=f"Terminal state protection: Case is already in terminal state '{case_status.value}'.",
                rules_evaluated=rules_evaluated,
            )

        # Rule 2: Security & Fraud Lock
        rules_evaluated.append("security_fraud_lock")
        if event.failure_code and "fraud" in event.failure_code.lower():
            return GuardrailResult(
                passed=False,
                status=GuardrailStatus.REJECTED,
                rejection_reason="Security policy violation: Auto-interventions blocked on security/fraud declines.",
                rules_evaluated=rules_evaluated,
            )

        # Rule 3: Explicit Human Review Requirement
        rules_evaluated.append("human_review_flag")
        if decision.requires_human or decision.recommended_action == InterventionType.HUMAN_ESCALATION:
            return GuardrailResult(
                passed=True,
                status=GuardrailStatus.HUMAN_REVIEW,
                rejection_reason="Intervention requires human review & approval.",
                rules_evaluated=rules_evaluated,
            )

        # Rule 4: Maximum Retry Budget Exhaustion
        rules_evaluated.append("retry_budget_check")
        if decision.recommended_action in (InterventionType.RETRY, InterventionType.DELAYED_RETRY):
            if attempts_completed >= self.MAX_RETRY_COUNT:
                return GuardrailResult(
                    passed=False,
                    status=GuardrailStatus.REJECTED,
                    rejection_reason=f"Retry budget exhausted: Max retry attempts ({self.MAX_RETRY_COUNT}) reached.",
                    rules_evaluated=rules_evaluated,
                )

        # Rule 5: Monetary Exposure Cap
        rules_evaluated.append("monetary_exposure_check")
        if event.amount > self.MAX_AUTO_EXPOSURE_INR:
            return GuardrailResult(
                passed=True,
                status=GuardrailStatus.HUMAN_REVIEW,
                rejection_reason=f"Monetary threshold flag: Amount (₹{event.amount:,.2f}) exceeds auto-approval limit (₹{self.MAX_AUTO_EXPOSURE_INR:,.2f}). Escalate to human operator.",
                rules_evaluated=rules_evaluated,
            )

        # Rule 6: Intervention Frequency Throttle
        rules_evaluated.append("contact_frequency_throttle")
        if context.last_intervention_at:
            elapsed_hours = (datetime.now(UTC) - context.last_intervention_at).total_seconds() / 3600.0
            if elapsed_hours < self.MIN_INTERVENTION_INTERVAL_HOURS:
                return GuardrailResult(
                    passed=False,
                    status=GuardrailStatus.REJECTED,
                    rejection_reason=f"Contact frequency limit: Last intervention was {elapsed_hours:.1f}h ago (minimum interval is {self.MIN_INTERVENTION_INTERVAL_HOURS}h).",
                    rules_evaluated=rules_evaluated,
                )

        # Rule 7: Action Whitelist Validation
        rules_evaluated.append("action_whitelist_check")
        if decision.recommended_action not in self.ALLOWED_ACTIONS:
            return GuardrailResult(
                passed=False,
                status=GuardrailStatus.REJECTED,
                rejection_reason=f"Policy violation: Action '{decision.recommended_action.value}' is not in the allowed action whitelist.",
                rules_evaluated=rules_evaluated,
            )

        # Rule 8: Low Confidence Floor
        rules_evaluated.append("confidence_floor_check")
        if prediction.recovery_probability < self.MIN_CONFIDENCE_THRESHOLD and decision.recommended_action != InterventionType.NO_ACTION:
            return GuardrailResult(
                passed=False,
                status=GuardrailStatus.REJECTED,
                rejection_reason=f"Confidence floor violation: Probability ({prediction.recovery_probability:.2f}) below threshold ({self.MIN_CONFIDENCE_THRESHOLD}).",
                rules_evaluated=rules_evaluated,
            )

        # All guardrail checks passed
        return GuardrailResult(
            passed=True,
            status=GuardrailStatus.APPROVED,
            rejection_reason=None,
            rules_evaluated=rules_evaluated,
        )
