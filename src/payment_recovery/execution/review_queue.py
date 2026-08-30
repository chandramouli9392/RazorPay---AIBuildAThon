from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from ..models import AuditRecord, InterventionType

_REVIEW_QUEUE: dict[str, dict[str, Any]] = {}


class HumanReviewQueue:
    """Manages manual review queue for uncertain or high-value recovery decisions."""

    def add_case_to_queue(self, audit_record: AuditRecord) -> dict[str, Any]:
        case_id = audit_record.event_id
        item = {
            "case_id": case_id,
            "audit_id": audit_record.audit_id,
            "customer_id": audit_record.customer_id,
            "leakage_type": audit_record.leakage_type.value,
            "amount_at_risk": audit_record.amount_at_risk,
            "root_cause": audit_record.root_cause.root_cause,
            "recovery_probability": audit_record.prediction.recovery_probability,
            "expected_recovery_value": audit_record.prediction.expected_recovery_value,
            "ai_recommended_action": audit_record.decision.recommended_action.value,
            "ai_reasoning": audit_record.decision.reasoning,
            "guardrail_status": audit_record.guardrail.status.value,
            "guardrail_rejection_reason": audit_record.guardrail.rejection_reason,
            "status": "pending_review",
            "queued_at": datetime.now(UTC).isoformat(),
            "audit_record": audit_record,
        }
        _REVIEW_QUEUE[case_id] = item
        return item

    def get_pending_cases(self) -> list[dict[str, Any]]:
        return [c for c in _REVIEW_QUEUE.values() if c["status"] == "pending_review"]

    def get_case(self, case_id: str) -> dict[str, Any] | None:
        return _REVIEW_QUEUE.get(case_id)

    def approve_case(self, case_id: str, reviewer: str = "human_operator") -> dict[str, Any]:
        item = _REVIEW_QUEUE.get(case_id)
        if not item:
            raise KeyError(f"Case {case_id} not found in review queue")
        item["status"] = "approved"
        item["reviewed_by"] = reviewer
        item["reviewed_at"] = datetime.now(UTC).isoformat()
        return item

    def reject_case(
        self, case_id: str, reason: str, reviewer: str = "human_operator"
    ) -> dict[str, Any]:
        item = _REVIEW_QUEUE.get(case_id)
        if not item:
            raise KeyError(f"Case {case_id} not found in review queue")
        item["status"] = "rejected"
        item["rejection_reason"] = reason
        item["reviewed_by"] = reviewer
        item["reviewed_at"] = datetime.now(UTC).isoformat()
        return item

    def modify_case(
        self, case_id: str, new_action: InterventionType, reviewer: str = "human_operator"
    ) -> dict[str, Any]:
        item = _REVIEW_QUEUE.get(case_id)
        if not item:
            raise KeyError(f"Case {case_id} not found in review queue")
        item["status"] = "modified"
        item["modified_action"] = new_action.value
        item["reviewed_by"] = reviewer
        item["reviewed_at"] = datetime.now(UTC).isoformat()
        return item
