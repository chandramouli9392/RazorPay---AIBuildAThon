from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from threading import Lock

from .models import NotificationKind, PolicyDecision, RecoveryStatus


@dataclass(frozen=True, slots=True)
class RecoveryCase:
    payment_intent_id: str
    status: RecoveryStatus
    attempts_completed: int = 0
    next_retry_at: datetime | None = None
    max_attempts: int = 0
    version: int = 1


@dataclass(frozen=True, slots=True)
class TransitionResult:
    case: RecoveryCase
    applied: bool
    duplicate: bool
    notification_required: bool = False


class RecoveryStore:
    """Thread-safe reference store demonstrating transition invariants.

    Production deployments use the PostgreSQL event and notification ledgers;
    this store keeps the deterministic state machine independently testable.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._cases: dict[str, RecoveryCase] = {}
        self._events: set[str] = set()
        self._notifications: set[tuple[str, NotificationKind]] = set()

    def apply_failure(
        self,
        event_id: str,
        payment_intent_id: str,
        decision: PolicyDecision,
    ) -> TransitionResult:
        with self._lock:
            existing = self._cases.get(payment_intent_id)
            if event_id in self._events:
                if existing is None:  # defensive invariant
                    raise RuntimeError("processed event has no recovery case")
                return TransitionResult(existing, applied=False, duplicate=True)
            self._events.add(event_id)
            if existing and existing.status in {RecoveryStatus.RECOVERED, RecoveryStatus.CANCELLED}:
                return TransitionResult(existing, applied=False, duplicate=False)

            status = (
                RecoveryStatus.PENDING
                if decision.retry_allowed
                else RecoveryStatus.MANUAL_REVIEW
                if decision.manual_review_required
                else RecoveryStatus.ACTION_REQUIRED
                if decision.max_attempts == 0 and decision.notification_required
                else RecoveryStatus.EXHAUSTED
            )
            notification_required = False
            if decision.notification_required and decision.notification_kind:
                notification_key = (payment_intent_id, decision.notification_kind)
                notification_required = notification_key not in self._notifications
                self._notifications.add(notification_key)

            case = RecoveryCase(
                payment_intent_id=payment_intent_id,
                status=status,
                attempts_completed=existing.attempts_completed if existing else 0,
                next_retry_at=decision.next_retry_at,
                max_attempts=decision.max_attempts,
                version=(existing.version + 1) if existing else 1,
            )
            self._cases[payment_intent_id] = case
            return TransitionResult(case, True, False, notification_required)

    def mark_attempt_failed(
        self, event_id: str, payment_intent_id: str, decision: PolicyDecision
    ) -> TransitionResult:
        with self._lock:
            case = self._require_case(payment_intent_id)
            if event_id in self._events:
                return TransitionResult(case, False, True)
            self._events.add(event_id)
            if case.status != RecoveryStatus.PENDING:
                return TransitionResult(case, False, False)
            status = RecoveryStatus.PENDING if decision.retry_allowed else RecoveryStatus.EXHAUSTED
            updated = replace(
                case,
                status=status,
                attempts_completed=case.attempts_completed + 1,
                next_retry_at=decision.next_retry_at,
                version=case.version + 1,
            )
            self._cases[payment_intent_id] = updated
            return TransitionResult(updated, True, False)

    def mark_recovered(self, event_id: str, payment_intent_id: str) -> TransitionResult:
        return self._terminal(event_id, payment_intent_id, RecoveryStatus.RECOVERED)

    def cancel(self, event_id: str, payment_intent_id: str) -> TransitionResult:
        return self._terminal(event_id, payment_intent_id, RecoveryStatus.CANCELLED)

    def get(self, payment_intent_id: str) -> RecoveryCase | None:
        with self._lock:
            return self._cases.get(payment_intent_id)

    def _terminal(
        self, event_id: str, payment_intent_id: str, status: RecoveryStatus
    ) -> TransitionResult:
        with self._lock:
            case = self._require_case(payment_intent_id)
            if event_id in self._events:
                return TransitionResult(case, False, True)
            self._events.add(event_id)
            if case.status in {RecoveryStatus.RECOVERED, RecoveryStatus.CANCELLED}:
                return TransitionResult(case, False, False)
            updated = replace(case, status=status, next_retry_at=None, version=case.version + 1)
            self._cases[payment_intent_id] = updated
            return TransitionResult(updated, True, False)

    def _require_case(self, payment_intent_id: str) -> RecoveryCase:
        try:
            return self._cases[payment_intent_id]
        except KeyError as exc:
            raise KeyError(f"unknown payment intent: {payment_intent_id}") from exc
