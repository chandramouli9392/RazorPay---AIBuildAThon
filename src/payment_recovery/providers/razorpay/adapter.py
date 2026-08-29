from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from ...models import (
    FailureCategory,
    LeakageType,
    NormalizedFailure,
    RazorpayFailure,
    RevenueEvent,
)
from ..base import BasePaymentProvider
from .client import RazorpayClientWrapper
from .signatures import verify_razorpay_signature

# Razorpay error_reason / error_code mappings to FailureCategory
SECURITY_REASONS = {
    "fraudulent",
    "stolen_card",
    "lost_card",
    "card_velocity_exceeded",
    "blacklisted_card",
    "risk_check_failed",
}

INVALID_METHOD_REASONS = {
    "expired_card",
    "invalid_card_number",
    "invalid_cvv",
    "invalid_expiry_date",
    "incorrect_cvv",
    "card_not_active",
}

AUTHENTICATION_REASONS = {
    "authentication_failed",
    "otp_expired",
    "otp_incorrect",
    "3d_secure_failed",
    "customer_cancelled",
}

TEMPORARY_REASONS = {
    "gateway_timeout",
    "bank_offline",
    "issuer_down",
    "network_error",
    "payment_processing_error",
    "try_again_later",
    "gateway_error",
}

INSUFFICIENT_FUNDS_REASONS = {
    "insufficient_funds",
    "low_balance",
    "credit_limit_exceeded",
    "account_overdrawn",
    "bad_request_error",
}

HARD_DECLINE_REASONS = {
    "do_not_honor",
    "account_blocked",
    "card_blocked",
    "transaction_not_allowed",
    "restriced_card",
}


def normalize_razorpay_failure(failure: RazorpayFailure) -> NormalizedFailure:
    """Map Razorpay specific error details into stable policy categories."""
    code = (failure.error_code or "").lower()
    reason_str = (failure.reason or failure.error_description or "").lower()
    desc = failure.error_description or "Razorpay payment failure"

    if any(s in reason_str or s in code for s in SECURITY_REASONS):
        category = FailureCategory.SECURITY_OR_FRAUD
        reason = f"Security/fraud signal: {desc}"
    elif any(s in reason_str or s in code for s in INVALID_METHOD_REASONS):
        category = FailureCategory.INVALID_PAYMENT_METHOD
        reason = f"Invalid payment method: {desc}"
    elif any(s in reason_str or s in code for s in AUTHENTICATION_REASONS):
        category = FailureCategory.AUTHENTICATION_REQUIRED
        reason = f"Customer authentication failed: {desc}"
    elif "insufficient" in reason_str or "low balance" in reason_str or code in INSUFFICIENT_FUNDS_REASONS:
        category = FailureCategory.INSUFFICIENT_FUNDS
        reason = f"Insufficient balance/funds: {desc}"
    elif "timeout" in reason_str or "temporary" in reason_str or code in TEMPORARY_REASONS or failure.source == "gateway":
        category = FailureCategory.TEMPORARY_PROCESSING
        reason = f"Temporary bank/gateway issue: {desc}"
    elif any(s in reason_str or s in code for s in HARD_DECLINE_REASONS):
        category = FailureCategory.HARD_DECLINE
        reason = f"Issuer hard decline: {desc}"
    else:
        category = FailureCategory.UNKNOWN
        reason = f"Unclassified decline code ({code}): {desc}"

    return NormalizedFailure(
        category=category,
        provider_code=code or "unknown",
        advice_code=failure.source,
        reason=reason,
    )


class RazorpayProviderAdapter(BasePaymentProvider):
    """Razorpay adapter implementing BasePaymentProvider interface."""

    def __init__(self, client_wrapper: RazorpayClientWrapper | None = None) -> None:
        self.client_wrapper = client_wrapper or RazorpayClientWrapper()

    @property
    def provider_name(self) -> str:
        return "razorpay"

    def verify_webhook_signature(
        self, raw_body: bytes, signature_header: str, secret: str
    ) -> bool:
        return verify_razorpay_signature(raw_body, signature_header, secret)

    def normalize_event(self, raw_payload: dict[str, Any]) -> RevenueEvent:
        """Convert raw Razorpay webhook payload into normalized RevenueEvent."""
        event_id = raw_payload.get("id") or f"evt_rzp_{int(datetime.now().timestamp())}"
        event_type = raw_payload.get("event", "payment.failed")
        created_at_ts = raw_payload.get("created_at") or int(datetime.now().timestamp())
        occurred_at = datetime.fromtimestamp(created_at_ts, tz=UTC)

        payload_content = raw_payload.get("payload", {})
        payment_entity = (
            payload_content.get("payment", {}).get("entity", {})
            or payload_content.get("order", {}).get("entity", {})
            or payload_content.get("subscription", {}).get("entity", {})
            or payload_content.get("invoice", {}).get("entity", {})
            or {}
        )

        customer_id = (
            payment_entity.get("customer_id")
            or payment_entity.get("customer", {}).get("id")
            or "cust_default_123"
        )
        payment_id = payment_entity.get("id")
        order_id = payment_entity.get("order_id") or payment_entity.get("id")
        subscription_id = payment_entity.get("subscription_id")
        invoice_id = payment_entity.get("invoice_id")

        amount_paise = payment_entity.get("amount", 0)
        amount_inr = float(amount_paise) / 100.0 if amount_paise else 0.0

        currency = payment_entity.get("currency", "INR")
        status = payment_entity.get("status", "failed")

        error_code = payment_entity.get("error_code")
        error_reason = payment_entity.get("error_reason") or payment_entity.get("error_description")

        if "subscription" in event_type or subscription_id:
            leakage_type = LeakageType.FAILED_SUBSCRIPTION
        elif "invoice" in event_type or invoice_id:
            leakage_type = LeakageType.OVERDUE_RECEIVABLE
        elif "order" in event_type and status in ("created", "attempted"):
            leakage_type = LeakageType.CHECKOUT_ABANDONMENT
        else:
            leakage_type = LeakageType.FAILED_PAYMENT

        return RevenueEvent(
            event_id=event_id,
            provider=self.provider_name,
            event_type=event_type,
            leakage_type=leakage_type,
            occurred_at=occurred_at,
            customer_id=customer_id,
            payment_id=payment_id,
            order_id=order_id,
            subscription_id=subscription_id,
            invoice_id=invoice_id,
            amount=amount_inr,
            currency=currency,
            status=status,
            failure_code=error_code,
            failure_reason=error_reason,
            metadata={
                "method": payment_entity.get("method"),
                "email": payment_entity.get("email"),
                "contact": payment_entity.get("contact"),
                "error_source": payment_entity.get("error_source"),
                "error_step": payment_entity.get("error_step"),
            },
            raw_payload=raw_payload,
            processed_at=datetime.now(UTC),
        )

    def create_payment_link(
        self, amount: float, currency: str, customer_id: str, description: str
    ) -> dict[str, Any]:
        return self.client_wrapper.create_payment_link(amount, currency, customer_id, description)

    def fetch_payment(self, payment_id: str) -> dict[str, Any]:
        return self.client_wrapper.fetch_payment(payment_id)

    def fetch_subscription(self, subscription_id: str) -> dict[str, Any]:
        return self.client_wrapper.fetch_subscription(subscription_id)

    def fetch_invoice(self, invoice_id: str) -> dict[str, Any]:
        return self.client_wrapper.fetch_invoice(invoice_id)
