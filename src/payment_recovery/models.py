from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class FailureCategory(StrEnum):
    INSUFFICIENT_FUNDS = "insufficient_funds"
    INVALID_PAYMENT_METHOD = "invalid_payment_method"
    AUTHENTICATION_REQUIRED = "authentication_required"
    SECURITY_OR_FRAUD = "security_or_fraud"
    TEMPORARY_PROCESSING = "temporary_processing"
    SUBSCRIPTION_HALTED = "subscription_halted"
    CHECKOUT_ABANDONED = "checkout_abandoned"
    INVOICE_OVERDUE = "invoice_overdue"
    HARD_DECLINE = "hard_decline"
    UNKNOWN = "unknown"


class LeakageType(StrEnum):
    FAILED_PAYMENT = "failed_payment"
    FAILED_SUBSCRIPTION = "failed_subscription"
    CHECKOUT_ABANDONMENT = "checkout_abandonment"
    OVERDUE_RECEIVABLE = "overdue_receivable"


class NotificationKind(StrEnum):
    INSUFFICIENT_FUNDS = "insufficient_funds"
    UPDATE_PAYMENT_METHOD = "update_payment_method"
    AUTHENTICATE_PAYMENT = "authenticate_payment"
    INTERNAL_SECURITY_REVIEW = "internal_security_review"
    MANUAL_REVIEW = "manual_review"
    RETRIES_EXHAUSTED = "retries_exhausted"
    PAYMENT_REMINDER = "payment_reminder"
    CHECKOUT_RECOVERY_LINK = "checkout_recovery_link"
    INVOICE_REMINDER = "invoice_reminder"


class RecoveryStatus(StrEnum):
    PENDING = "pending"
    ACTION_REQUIRED = "action_required"
    MANUAL_REVIEW = "manual_review"
    RECOVERED = "recovered"
    EXHAUSTED = "exhausted"
    CANCELLED = "cancelled"
    EXECUTING = "executing"
    INTERVENTION_SENT = "intervention_sent"


class InterventionType(StrEnum):
    RETRY = "retry"
    DELAYED_RETRY = "delayed_retry"
    UPDATE_PAYMENT_METHOD = "update_payment_method"
    PAYMENT_REMINDER = "payment_reminder"
    PERSONALIZED_MESSAGE = "personalized_message"
    CHECKOUT_RECOVERY = "checkout_recovery"
    INVOICE_REMINDER = "invoice_reminder"
    HUMAN_ESCALATION = "human_escalation"
    NO_ACTION = "no_action"


class GuardrailStatus(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"
    HUMAN_REVIEW = "human_review"


@dataclass(frozen=True, slots=True)
class RazorpayFailure:
    error_code: str | None = None
    error_description: str | None = None
    reason: str | None = None
    field: str | None = None
    source: str | None = None
    step: str | None = None
    decline_code: str | None = None
    advice_code: str | None = None
    network_advice_code: str | None = None


@dataclass(frozen=True, slots=True)
class StripeFailure:
    error_code: str | None = None
    decline_code: str | None = None
    advice_code: str | None = None
    network_advice_code: str | None = None


@dataclass(frozen=True, slots=True)
class NormalizedFailure:
    category: FailureCategory
    provider_code: str
    advice_code: str | None
    reason: str


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    category: FailureCategory
    retry_allowed: bool
    next_retry_at: datetime | None
    max_attempts: int
    notification_required: bool
    notification_kind: NotificationKind | None
    manual_review_required: bool
    reason: str
    policy_version: str = "2026-08-23"


@dataclass(slots=True)
class RevenueEvent:
    event_id: str
    provider: str
    event_type: str
    leakage_type: LeakageType
    occurred_at: datetime
    customer_id: str
    payment_id: str | None = None
    order_id: str | None = None
    subscription_id: str | None = None
    invoice_id: str | None = None
    amount: float = 0.0  # in INR ₹
    currency: str = "INR"
    status: str = "failed"
    failure_code: str | None = None
    failure_reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    raw_payload: dict[str, Any] = field(default_factory=dict)
    processed_at: datetime | None = None


@dataclass(slots=True)
class CustomerRevenueContext:
    customer_id: str
    name: str
    email: str
    ltv: float
    historical_success_rate: float
    total_payments_count: int
    previous_failures_count: int
    previous_recoveries_count: int
    avg_transaction_amount: float
    subscription_tenure_days: int
    days_overdue: int
    segment: str  # e.g., "VIP", "Standard", "At-Risk", "New"
    previous_interventions_count: int
    last_intervention_at: datetime | None = None
    response_to_past_interventions_rate: float = 0.0


@dataclass(slots=True)
class RootCauseAnalysis:
    root_cause: str
    category: FailureCategory
    confidence: float
    evidence: list[str]
    recoverability: str  # "HIGH", "MEDIUM", "LOW", "UNRECOVERABLE"
    recommended_next_step: str


@dataclass(slots=True)
class RecoveryPrediction:
    recovery_probability: float
    confidence: float
    expected_recovery_value: float
    top_contributing_features: list[dict[str, Any]]
    model_version: str = "v1.0.0-rf"


@dataclass(slots=True)
class CandidateInterventionEvaluation:
    action_type: InterventionType
    predicted_probability: float
    expected_recovery_value: float
    estimated_cost: float
    friction_penalty: float
    net_expected_value: float
    recommended: bool
    status: GuardrailStatus
    rejection_reason: str | None = None


@dataclass(slots=True)
class InterventionDecision:
    decision_id: str
    recommended_action: InterventionType
    reasoning: str
    expected_net_recovery: float
    estimated_cost: float
    timing_delay_hours: int = 0
    personalized_copy: str | None = None
    requires_human: bool = False
    candidate_evaluations: list[CandidateInterventionEvaluation] = field(default_factory=list)


@dataclass(slots=True)
class GuardrailResult:
    passed: bool
    status: GuardrailStatus
    rejection_reason: str | None = None
    rules_evaluated: list[str] = field(default_factory=list)
    policy_version: str = "2026-08-23"


@dataclass(slots=True)
class ActionExecution:
    action_id: str
    event_id: str
    customer_id: str
    action_type: InterventionType
    executed_at: datetime
    status: str  # "executed", "simulated", "failed"
    amount_at_risk: float
    expected_recovery: float
    actual_recovery: float = 0.0
    provider_response_id: str | None = None
    is_simulation: bool = True


@dataclass(slots=True)
class AuditRecord:
    audit_id: str
    timestamp: datetime
    event_id: str
    customer_id: str
    leakage_type: LeakageType
    amount_at_risk: float
    root_cause: RootCauseAnalysis
    prediction: RecoveryPrediction
    decision: InterventionDecision
    guardrail: GuardrailResult
    action: ActionExecution | None = None
    baseline_action: str = "fixed_retry"
    baseline_expected_recovery: float = 0.0
    incremental_recovery_value: float = 0.0
