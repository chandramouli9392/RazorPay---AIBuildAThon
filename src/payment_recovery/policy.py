from __future__ import annotations

from datetime import UTC, datetime, timedelta

from .models import FailureCategory, NormalizedFailure, NotificationKind, PolicyDecision


class RecoveryPolicy:
    """Conservative, deterministic retry policy.

    `attempts_completed` counts automated recovery attempts already made, not
    the original failed payment.
    """

    _SCHEDULES = {
        FailureCategory.INSUFFICIENT_FUNDS: (
            timedelta(hours=48),
            timedelta(hours=120),
            timedelta(hours=168),
        ),
        FailureCategory.TEMPORARY_PROCESSING: (
            timedelta(hours=1),
            timedelta(hours=6),
            timedelta(hours=24),
        ),
    }

    def decide(
        self,
        failure: NormalizedFailure,
        *,
        attempts_completed: int,
        occurred_at: datetime,
    ) -> PolicyDecision:
        if attempts_completed < 0:
            raise ValueError("attempts_completed cannot be negative")
        if occurred_at.tzinfo is None or occurred_at.utcoffset() is None:
            raise ValueError("occurred_at must be timezone-aware")
        occurred_at = occurred_at.astimezone(UTC)

        schedule = self._SCHEDULES.get(failure.category, ())
        max_attempts = len(schedule)
        retry_allowed = attempts_completed < max_attempts
        next_retry_at = occurred_at + schedule[attempts_completed] if retry_allowed else None

        notification_kind: NotificationKind | None
        manual_review = False
        if failure.category == FailureCategory.INSUFFICIENT_FUNDS:
            notification_kind = (
                NotificationKind.INSUFFICIENT_FUNDS
                if retry_allowed
                else NotificationKind.RETRIES_EXHAUSTED
            )
        elif failure.category == FailureCategory.TEMPORARY_PROCESSING:
            notification_kind = None if retry_allowed else NotificationKind.RETRIES_EXHAUSTED
        elif failure.category == FailureCategory.INVALID_PAYMENT_METHOD:
            notification_kind = NotificationKind.UPDATE_PAYMENT_METHOD
        elif failure.category == FailureCategory.AUTHENTICATION_REQUIRED:
            notification_kind = NotificationKind.AUTHENTICATE_PAYMENT
        elif failure.category == FailureCategory.SECURITY_OR_FRAUD:
            notification_kind = NotificationKind.INTERNAL_SECURITY_REVIEW
            manual_review = True
        else:
            notification_kind = NotificationKind.MANUAL_REVIEW
            manual_review = True

        return PolicyDecision(
            category=failure.category,
            retry_allowed=retry_allowed,
            next_retry_at=next_retry_at,
            max_attempts=max_attempts,
            notification_required=notification_kind is not None,
            notification_kind=notification_kind,
            manual_review_required=manual_review,
            reason=failure.reason
            if retry_allowed or max_attempts == 0
            else "Automated retry budget exhausted",
        )
