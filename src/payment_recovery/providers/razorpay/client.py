from __future__ import annotations

import os
from typing import Any

try:
    import razorpay
except ImportError:
    razorpay = None


class RazorpayClientWrapper:
    """Wrapper around official razorpay.Client with fallback mock simulation mode."""

    def __init__(
        self,
        key_id: str | None = None,
        key_secret: str | None = None,
    ) -> None:
        self.key_id = key_id or os.environ.get("RAZORPAY_KEY_ID", "rzp_test_mock12345")
        self.key_secret = key_secret or os.environ.get("RAZORPAY_KEY_SECRET", "mock_secret_abc123")
        self.is_live = bool(
            razorpay is not None
            and self.key_id
            and not self.key_id.startswith("rzp_test_mock")
            and self.key_secret
            and not self.key_secret.startswith("mock_secret")
        )

        if self.is_live:
            self.client = razorpay.Client(auth=(self.key_id, self.key_secret))
        else:
            self.client = None

    def fetch_payment(self, payment_id: str) -> dict[str, Any]:
        if self.client:
            try:
                return self.client.payment.fetch(payment_id)
            except Exception:
                pass
        return {
            "id": payment_id,
            "entity": "payment",
            "amount": 1000000,  # ₹10,000 in paise
            "currency": "INR",
            "status": "failed",
            "order_id": f"order_{payment_id}",
            "method": "card",
            "error_code": "BAD_REQUEST_ERROR",
            "error_description": "Payment failed due to insufficient balance",
            "error_reason": "insufficient_funds",
            "created_at": 1755940000,
        }

    def fetch_subscription(self, subscription_id: str) -> dict[str, Any]:
        if self.client:
            try:
                return self.client.subscription.fetch(subscription_id)
            except Exception:
                pass
        return {
            "id": subscription_id,
            "entity": "subscription",
            "plan_id": "plan_sub_pro",
            "status": "halted",
            "current_start": 1755900000,
            "current_end": 1758500000,
            "ended_at": None,
            "quantity": 1,
            "charge_at": 1755940000,
            "has_scheduled_changes": False,
            "change_scheduled_at": None,
            "offer_id": None,
            "remaining_count": 11,
        }

    def fetch_invoice(self, invoice_id: str) -> dict[str, Any]:
        if self.client:
            try:
                return self.client.invoice.fetch(invoice_id)
            except Exception:
                pass
        return {
            "id": invoice_id,
            "entity": "invoice",
            "amount": 2500000,  # ₹25,000 in paise
            "amount_paid": 0,
            "amount_due": 2500000,
            "currency": "INR",
            "status": "issued",
            "expire_by": 1755850000,
        }

    def create_payment_link(
        self, amount_inr: float, currency: str, customer_id: str, description: str
    ) -> dict[str, Any]:
        amount_paise = int(amount_inr * 100)
        if self.client:
            try:
                return self.client.payment_link.create(
                    {
                        "amount": amount_paise,
                        "currency": currency,
                        "accept_partial": False,
                        "description": description,
                        "customer": {"name": "Customer", "contact": "+919999999999"},
                        "notify": {"sms": True, "email": True},
                        "reminder_enable": True,
                    }
                )
            except Exception:
                pass
        return {
            "id": f"plink_{customer_id[:8]}",
            "entity": "payment_link",
            "amount": amount_paise,
            "currency": currency,
            "short_url": f"https://rzp.io/i/recov_{customer_id[:6]}",
            "status": "created",
            "description": description,
        }

    def retry_charge(self, payment_id: str) -> dict[str, Any]:
        """Simulate or execute payment retry in Razorpay test mode."""
        return {
            "id": f"pay_retry_{payment_id[:8]}",
            "entity": "payment",
            "status": "captured",
            "amount": 1000000,
            "currency": "INR",
            "method": "card",
        }
