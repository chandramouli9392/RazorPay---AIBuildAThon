from __future__ import annotations

from ..models import (
    CustomerRevenueContext,
    FailureCategory,
    LeakageType,
    RazorpayFailure,
    RevenueEvent,
    RootCauseAnalysis,
)
from ..providers.razorpay.adapter import normalize_razorpay_failure


class RootCauseAnalysisAgent:
    """Root Cause AI Agent analyzing failure cause from verified system data."""

    def diagnose(self, event: RevenueEvent, context: CustomerRevenueContext) -> RootCauseAnalysis:
        """Perform structured diagnosis over event payload and customer context."""
        failure = RazorpayFailure(
            error_code=event.failure_code,
            error_description=event.failure_reason,
            reason=event.failure_reason or event.failure_code,
            source=event.metadata.get("error_source"),
            step=event.metadata.get("error_step"),
        )
        normalized = normalize_razorpay_failure(failure)
        category = normalized.category

        evidence = [
            f"Provider code: '{event.failure_code or 'N/A'}'",
            f"Provider reason: '{event.failure_reason or 'N/A'}'",
            f"Customer LTV: ₹{context.ltv:,.2f} ({context.segment} segment)",
            f"Historical payment success rate: {int(context.historical_success_rate * 100)}%",
            f"Previous failures: {context.previous_failures_count}, "
            f"recoveries: {context.previous_recoveries_count}",
        ]

        # Handle specific leakage types
        if event.leakage_type == LeakageType.CHECKOUT_ABANDONMENT:
            return RootCauseAnalysis(
                root_cause="Customer abandoned checkout before completing authorization",
                category=FailureCategory.CHECKOUT_ABANDONED,
                confidence=0.92,
                evidence=evidence
                + ["Checkout order created but authorization step was not completed"],
                recoverability=("HIGH" if context.historical_success_rate > 0.6 else "MEDIUM"),
                recommended_next_step=(
                    "Send automated personalized checkout recovery link via WhatsApp/Email"
                ),
            )

        if event.leakage_type == LeakageType.OVERDUE_RECEIVABLE:
            return RootCauseAnalysis(
                root_cause=f"Invoice receivable past due date by {context.days_overdue} days",
                category=FailureCategory.INVOICE_OVERDUE,
                confidence=0.95,
                evidence=evidence + [f"Invoice unpaid for {context.days_overdue} days"],
                recoverability="HIGH" if context.ltv > 20000 else "MEDIUM",
                recommended_next_step=(
                    "Send gentle payment reminder notice with direct 1-click Razorpay payment link"
                ),
            )

        if category == FailureCategory.INSUFFICIENT_FUNDS:
            confidence = 0.94
            recoverability = "HIGH" if context.historical_success_rate > 0.7 else "MEDIUM"
            return RootCauseAnalysis(
                root_cause="Temporary balance shortfall on customer payment account/card",
                category=category,
                confidence=confidence,
                evidence=evidence + ["Issuer returned insufficient balance error"],
                recoverability=recoverability,
                recommended_next_step=(
                    "Schedule bounded delayed retries aligned with payday (48h / 120h schedule)"
                ),
            )

        if category == FailureCategory.TEMPORARY_PROCESSING:
            return RootCauseAnalysis(
                root_cause=(
                    "Temporary processing/gateway connectivity interruption between bank & issuer"
                ),
                category=category,
                confidence=0.89,
                evidence=evidence + ["Gateway or bank system reported transient timeout/error"],
                recoverability="HIGH",
                recommended_next_step="Schedule short-interval automatic retry (1h / 6h schedule)",
            )

        if category == FailureCategory.INVALID_PAYMENT_METHOD:
            return RootCauseAnalysis(
                root_cause="Customer card or payment method expired or details invalidated",
                category=category,
                confidence=0.96,
                evidence=evidence + ["Issuer returned expired/invalid payment method code"],
                recoverability="MEDIUM",
                recommended_next_step=(
                    "Request customer to update payment method details via secure Razorpay portal"
                ),
            )

        if category == FailureCategory.AUTHENTICATION_REQUIRED:
            return RootCauseAnalysis(
                root_cause=(
                    "Customer 3D-Secure or OTP authentication was required but not completed"
                ),
                category=category,
                confidence=0.91,
                evidence=evidence + ["Authentication step timed out or was abandoned by user"],
                recoverability="HIGH",
                recommended_next_step="Prompt customer to complete authentication via push notification/SMS",
            )

        if category == FailureCategory.SECURITY_OR_FRAUD:
            return RootCauseAnalysis(
                root_cause=(
                    "Provider or issuer security system flagged transaction for security review"
                ),
                category=category,
                confidence=0.98,
                evidence=evidence + ["Security/fraud decline code observed"],
                recoverability="UNRECOVERABLE",
                recommended_next_step="Flag for internal risk manual review. Do not auto-retry.",
            )

        if category == FailureCategory.HARD_DECLINE:
            return RootCauseAnalysis(
                root_cause="Issuer issued explicit do-not-retry hard decline",
                category=category,
                confidence=0.95,
                evidence=evidence + ["Hard decline code issued by bank"],
                recoverability="LOW",
                recommended_next_step="Request alternative payment method from customer.",
            )

        # Fallback / Unknown
        return RootCauseAnalysis(
            root_cause="Unspecified issuer or network decline reason",
            category=FailureCategory.UNKNOWN,
            confidence=0.70,
            evidence=evidence,
            recoverability=("MEDIUM" if context.historical_success_rate > 0.75 else "LOW"),
            recommended_next_step="Perform single delayed retry or request manual operational review",
        )
