from datetime import UTC, datetime, timedelta

import pytest

from payment_recovery.models import FailureCategory, NormalizedFailure, NotificationKind
from payment_recovery.policy import RecoveryPolicy

NOW = datetime(2026, 8, 9, 12, tzinfo=UTC)


def failure(category: FailureCategory) -> NormalizedFailure:
    return NormalizedFailure(category, category.value, None, "test reason")


def test_insufficient_funds_has_bounded_deterministic_schedule():
    policy = RecoveryPolicy()
    expected = [timedelta(hours=48), timedelta(hours=120), timedelta(hours=168)]
    for attempts, offset in enumerate(expected):
        decision = policy.decide(
            failure(FailureCategory.INSUFFICIENT_FUNDS),
            attempts_completed=attempts,
            occurred_at=NOW,
        )
        assert decision.retry_allowed
        assert decision.next_retry_at == NOW + offset
        assert decision.max_attempts == 3


def test_exhausted_budget_has_no_next_retry():
    decision = RecoveryPolicy().decide(
        failure(FailureCategory.INSUFFICIENT_FUNDS), attempts_completed=3, occurred_at=NOW
    )
    assert not decision.retry_allowed
    assert decision.next_retry_at is None
    assert decision.notification_kind == NotificationKind.RETRIES_EXHAUSTED


@pytest.mark.parametrize(
    "category",
    [
        FailureCategory.SECURITY_OR_FRAUD,
        FailureCategory.HARD_DECLINE,
        FailureCategory.UNKNOWN,
        FailureCategory.INVALID_PAYMENT_METHOD,
        FailureCategory.AUTHENTICATION_REQUIRED,
    ],
)
def test_customer_or_manual_action_categories_are_not_blindly_retried(category):
    decision = RecoveryPolicy().decide(failure(category), attempts_completed=0, occurred_at=NOW)
    assert not decision.retry_allowed
    assert decision.next_retry_at is None
    assert decision.max_attempts == 0


def test_security_decline_requires_internal_review_not_customer_fraud_disclosure():
    decision = RecoveryPolicy().decide(
        failure(FailureCategory.SECURITY_OR_FRAUD), attempts_completed=0, occurred_at=NOW
    )
    assert decision.manual_review_required
    assert decision.notification_kind == NotificationKind.INTERNAL_SECURITY_REVIEW


def test_temporary_processing_uses_short_bounded_schedule():
    decision = RecoveryPolicy().decide(
        failure(FailureCategory.TEMPORARY_PROCESSING), attempts_completed=1, occurred_at=NOW
    )
    assert decision.next_retry_at == NOW + timedelta(hours=6)
    assert decision.max_attempts == 3


def test_rejects_negative_attempt_count_and_naive_time():
    policy = RecoveryPolicy()
    with pytest.raises(ValueError, match="negative"):
        policy.decide(failure(FailureCategory.UNKNOWN), attempts_completed=-1, occurred_at=NOW)
    with pytest.raises(ValueError, match="timezone-aware"):
        policy.decide(
            failure(FailureCategory.UNKNOWN),
            attempts_completed=0,
            occurred_at=NOW.replace(tzinfo=None),
        )
