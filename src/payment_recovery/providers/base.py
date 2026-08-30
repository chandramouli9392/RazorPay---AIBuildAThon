from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..models import RevenueEvent


class BasePaymentProvider(ABC):
    """Abstract base class for payment gateway providers."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name of the provider (e.g., 'razorpay')."""

    @abstractmethod
    def verify_webhook_signature(self, raw_body: bytes, signature_header: str, secret: str) -> bool:
        """Verify webhook signature using raw body bytes."""

    @abstractmethod
    def normalize_event(self, raw_payload: dict[str, Any]) -> RevenueEvent:
        """Normalize raw webhook payload into internal RevenueEvent."""

    @abstractmethod
    def create_payment_link(
        self, amount: float, currency: str, customer_id: str, description: str
    ) -> dict[str, Any]:
        """Create a payment recovery link for customer interaction."""

    @abstractmethod
    def fetch_payment(self, payment_id: str) -> dict[str, Any]:
        """Fetch payment details from provider."""

    @abstractmethod
    def fetch_subscription(self, subscription_id: str) -> dict[str, Any]:
        """Fetch subscription details from provider."""

    @abstractmethod
    def fetch_invoice(self, invoice_id: str) -> dict[str, Any]:
        """Fetch invoice details from provider."""
