from __future__ import annotations

import uuid
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any

from ..models import (
    ActionExecution,
    AuditRecord,
    CustomerRevenueContext,
    GuardrailResult,
    InterventionDecision,
    RecoveryPrediction,
    RevenueEvent,
    RootCauseAnalysis,
)

_AUDIT_LOG_STORE: dict[str, AuditRecord] = {}


class RecoveryAuditLogger:
    """Immutable audit logging engine for end-to-end explainability of financial interventions."""

    def log_decision_pipeline(
        self,
        event: RevenueEvent,
        context: CustomerRevenueContext,
        root_cause: RootCauseAnalysis,
        prediction: RecoveryPrediction,
        decision: InterventionDecision,
        guardrail: GuardrailResult,
        action: ActionExecution | None = None,
        baseline_action: str = "fixed_retry",
    ) -> AuditRecord:
        audit_id = f"aud_{uuid.uuid4().hex[:12]}"

        # Calculate baseline expected recovery for counterfactual comparison
        # Baseline strategy (fixed 3 retries): recovers ~35% of insufficient funds & temporary processing only
        if root_cause.category in ("insufficient_funds", "temporary_processing"):
            baseline_prob = 0.35
        else:
            baseline_prob = 0.0
        baseline_expected = round(event.amount * baseline_prob, 2)

        actual_recovery = action.actual_recovery if action else 0.0
        incremental_value = round(max(0.0, actual_recovery - baseline_expected), 2)

        record = AuditRecord(
            audit_id=audit_id,
            timestamp=datetime.now(UTC),
            event_id=event.event_id,
            customer_id=event.customer_id,
            leakage_type=event.leakage_type,
            amount_at_risk=event.amount,
            root_cause=root_cause,
            prediction=prediction,
            decision=decision,
            guardrail=guardrail,
            action=action,
            baseline_action=baseline_action,
            baseline_expected_recovery=baseline_expected,
            incremental_recovery_value=incremental_value,
        )

        _AUDIT_LOG_STORE[audit_id] = record
        _AUDIT_LOG_STORE[event.event_id] = record
        return record

    def get_audit_record(self, key: str) -> AuditRecord | None:
        return _AUDIT_LOG_STORE.get(key)

    def get_all_records(self) -> list[AuditRecord]:
        # Return unique records
        seen = set()
        records = []
        for r in _AUDIT_LOG_STORE.values():
            if r.audit_id not in seen:
                seen.add(r.audit_id)
                records.append(r)
        return records

    def export_record_as_json(self, key: str) -> dict[str, Any] | None:
        record = self.get_audit_record(key)
        if not record:
            return None
        return asdict(record)
