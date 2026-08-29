from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from ..models import (
    ActionExecution,
    CustomerRevenueContext,
    GuardrailResult,
    GuardrailStatus,
    InterventionDecision,
    InterventionType,
    RecoveryPrediction,
    RevenueEvent,
)
from ..providers.razorpay.adapter import RazorpayProviderAdapter

_EXECUTED_ACTIONS: dict[str, ActionExecution] = {}


class RecoveryExecutionEngine:
    """Controlled execution layer dispatching approved interventions via Razorpay SDK/simulation."""

    def __init__(self, provider_adapter: RazorpayProviderAdapter | None = None) -> None:
        self.provider = provider_adapter or RazorpayProviderAdapter()

    def execute_action(
        self,
        event: RevenueEvent,
        context: CustomerRevenueContext,
        decision: InterventionDecision,
        prediction: RecoveryPrediction,
        guardrail: GuardrailResult,
    ) -> ActionExecution:
        action_id = f"act_{uuid.uuid4().hex[:10]}"

        # Idempotency check: if action already executed for event_id, return cached result
        if event.event_id in _EXECUTED_ACTIONS:
            return _EXECUTED_ACTIONS[event.event_id]

        if not guardrail.passed or guardrail.status != GuardrailStatus.APPROVED:
            execution = ActionExecution(
                action_id=action_id,
                event_id=event.event_id,
                customer_id=event.customer_id,
                action_type=decision.recommended_action,
                executed_at=datetime.now(UTC),
                status="blocked_by_guardrail",
                amount_at_risk=event.amount,
                expected_recovery=0.0,
                actual_recovery=0.0,
                provider_response_id=None,
                is_simulation=True,
            )
            _EXECUTED_ACTIONS[event.event_id] = execution
            return execution

        action_type = decision.recommended_action
        provider_resp_id: str | None = None

        if action_type in (InterventionType.CHECKOUT_RECOVERY, InterventionType.INVOICE_REMINDER, InterventionType.UPDATE_PAYMENT_METHOD):
            link = self.provider.create_payment_link(
                amount=event.amount,
                currency=event.currency,
                customer_id=event.customer_id,
                description=f"Recovery link for {event.event_id}",
            )
            provider_resp_id = link.get("id")

        elif action_type in (InterventionType.RETRY, InterventionType.DELAYED_RETRY):
            retry_res = self.provider.client_wrapper.retry_charge(event.payment_id or event.event_id)
            provider_resp_id = retry_res.get("id")

        # Simulate outcome recovery amount based on predicted probability
        actual_rec = event.amount if prediction.recovery_probability >= 0.40 else 0.0

        execution = ActionExecution(
            action_id=action_id,
            event_id=event.event_id,
            customer_id=event.customer_id,
            action_type=action_type,
            executed_at=datetime.now(UTC),
            status="executed",
            amount_at_risk=event.amount,
            expected_recovery=prediction.expected_recovery_value,
            actual_recovery=actual_rec,
            provider_response_id=provider_resp_id or f"rzp_mock_{action_id}",
            is_simulation=True,
        )

        _EXECUTED_ACTIONS[event.event_id] = execution
        return execution


def get_action_execution(event_id: str) -> ActionExecution | None:
    return _EXECUTED_ACTIONS.get(event_id)
