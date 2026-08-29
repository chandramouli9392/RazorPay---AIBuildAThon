from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from payment_recovery.models import FailureCategory, NormalizedFailure, RecoveryStatus
from payment_recovery.policy import RecoveryPolicy
from payment_recovery.state_machine import RecoveryStore

NOW = datetime(2026, 8, 9, tzinfo=UTC)


def decision(category=FailureCategory.INSUFFICIENT_FUNDS, attempts=0):
    normalized = NormalizedFailure(category, category.value, None, "test")
    return RecoveryPolicy().decide(normalized, attempts_completed=attempts, occurred_at=NOW)


def test_duplicate_webhook_is_idempotent():
    store = RecoveryStore()
    first = store.apply_failure("evt_1", "pi_1", decision())
    replay = store.apply_failure("evt_1", "pi_1", decision())
    assert first.applied and first.notification_required
    assert replay.duplicate and not replay.applied
    assert replay.case.version == 1


def test_distinct_replayed_failure_deduplicates_notification():
    store = RecoveryStore()
    first = store.apply_failure("evt_1", "pi_1", decision())
    second = store.apply_failure("evt_2", "pi_1", decision())
    assert first.notification_required
    assert not second.notification_required
    assert second.case.version == 2


def test_success_cancels_future_retry_and_late_failure_cannot_reopen_case():
    store = RecoveryStore()
    store.apply_failure("evt_fail", "pi_1", decision())
    recovered = store.mark_recovered("evt_success", "pi_1")
    late = store.apply_failure("evt_late", "pi_1", decision())
    assert recovered.case.status == RecoveryStatus.RECOVERED
    assert recovered.case.next_retry_at is None
    assert not late.applied
    assert late.case.status == RecoveryStatus.RECOVERED


def test_cancellation_clears_retry_and_is_terminal():
    store = RecoveryStore()
    store.apply_failure("evt_fail", "pi_1", decision())
    cancelled = store.cancel("evt_cancel", "pi_1")
    assert cancelled.case.status == RecoveryStatus.CANCELLED
    assert cancelled.case.next_retry_at is None
    assert not store.mark_recovered("evt_success", "pi_1").applied


def test_failed_attempt_increments_once_and_exhausts_budget():
    store = RecoveryStore()
    store.apply_failure("evt_fail", "pi_1", decision())
    store.mark_attempt_failed("evt_retry_1", "pi_1", decision(attempts=1))
    store.mark_attempt_failed("evt_retry_2", "pi_1", decision(attempts=2))
    exhausted = store.mark_attempt_failed("evt_retry_3", "pi_1", decision(attempts=3))
    replay = store.mark_attempt_failed("evt_retry_3", "pi_1", decision(attempts=3))
    assert exhausted.case.attempts_completed == 3
    assert exhausted.case.status == RecoveryStatus.EXHAUSTED
    assert exhausted.case.next_retry_at is None
    assert replay.duplicate


def test_concurrent_duplicate_delivery_applies_exactly_once():
    store = RecoveryStore()

    def deliver(_):
        return store.apply_failure("evt_same", "pi_1", decision())

    with ThreadPoolExecutor(max_workers=16) as executor:
        results = list(executor.map(deliver, range(64)))
    assert sum(result.applied for result in results) == 1
    assert sum(result.duplicate for result in results) == 63
    assert store.get("pi_1").version == 1


def test_concurrent_success_and_failure_end_recovered_without_future_retry():
    store = RecoveryStore()
    store.apply_failure("evt_initial", "pi_1", decision())

    def deliver(index):
        if index == 0:
            return store.mark_recovered("evt_success", "pi_1")
        return store.apply_failure(f"evt_late_{index}", "pi_1", decision())

    with ThreadPoolExecutor(max_workers=16) as executor:
        list(executor.map(deliver, range(32)))
    case = store.get("pi_1")
    assert case.status == RecoveryStatus.RECOVERED
    assert case.next_retry_at is None


def test_security_failure_enters_manual_review():
    store = RecoveryStore()
    result = store.apply_failure(
        "evt_security", "pi_security", decision(FailureCategory.SECURITY_OR_FRAUD)
    )
    assert result.case.status == RecoveryStatus.MANUAL_REVIEW
    assert result.case.next_retry_at is None


def test_expired_card_enters_customer_action_state():
    store = RecoveryStore()
    result = store.apply_failure(
        "evt_expired", "pi_expired", decision(FailureCategory.INVALID_PAYMENT_METHOD)
    )
    assert result.case.status == RecoveryStatus.ACTION_REQUIRED
    assert result.case.next_retry_at is None
