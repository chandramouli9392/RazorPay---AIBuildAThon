from __future__ import annotations

from typing import Any

from ..models import LeakageType, RevenueEvent


class RevenueLeakageDetector:
    """Detects and categorizes revenue at risk across 4 primary leakage scenarios."""

    def analyze_event(self, event: RevenueEvent) -> dict[str, Any]:
        """Analyze a RevenueEvent and return leakage classification with risk assessment."""
        leakage_type = self._determine_leakage_type(event)
        risk_score = self._compute_risk_score(event, leakage_type)

        return {
            "event_id": event.event_id,
            "leakage_type": leakage_type,
            "amount_at_risk": event.amount,
            "currency": event.currency,
            "risk_score": risk_score,
            "description": self._describe_leakage(event, leakage_type),
            "requires_intervention": event.amount > 0 and status_is_recoverable(event.status),
        }

    def _determine_leakage_type(self, event: RevenueEvent) -> LeakageType:
        if event.leakage_type:
            return event.leakage_type

        if event.subscription_id or "subscription" in event.event_type:
            return LeakageType.FAILED_SUBSCRIPTION
        if event.invoice_id or "invoice" in event.event_type:
            return LeakageType.OVERDUE_RECEIVABLE
        if "order" in event.event_type or "checkout" in event.event_type:
            return LeakageType.CHECKOUT_ABANDONMENT
        return LeakageType.FAILED_PAYMENT

    def _compute_risk_score(self, event: RevenueEvent, leakage_type: LeakageType) -> float:
        """Calculate a risk urgency score from 0.0 (low) to 1.0 (critical)."""
        base = 0.5
        if event.amount >= 20000:
            base += 0.3
        elif event.amount >= 5000:
            base += 0.15

        if leakage_type == LeakageType.FAILED_SUBSCRIPTION:
            base += 0.1  # High LTV impact
        elif leakage_type == LeakageType.OVERDUE_RECEIVABLE:
            base += 0.15
        elif leakage_type == LeakageType.CHECKOUT_ABANDONMENT:
            base += 0.05

        return min(round(base, 2), 1.0)

    def _describe_leakage(self, event: RevenueEvent, leakage_type: LeakageType) -> str:
        amt = f"₹{event.amount:,.2f}"
        if leakage_type == LeakageType.FAILED_PAYMENT:
            return f"Payment of {amt} failed due to {event.failure_reason or 'declined transaction'}."
        if leakage_type == LeakageType.FAILED_SUBSCRIPTION:
            return f"Recurring subscription charge of {amt} failed (Sub ID: {event.subscription_id or 'N/A'})."
        if leakage_type == LeakageType.CHECKOUT_ABANDONMENT:
            return f"Checkout session for {amt} was abandoned prior to payment completion."
        if leakage_type == LeakageType.OVERDUE_RECEIVABLE:
            return f"Invoice receivable of {amt} is overdue (Inv ID: {event.invoice_id or 'N/A'})."
        return f"Revenue at risk: {amt}"


def status_is_recoverable(status: str) -> bool:
    """Check if transaction status is eligible for recovery intervention."""
    return status.lower() in (
        "failed",
        "halted",
        "issued",
        "overdue",
        "created",
        "partially_paid",
        "attempted",
    )
