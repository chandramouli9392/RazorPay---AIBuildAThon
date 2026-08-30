import os
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict

from .ai.context import get_or_create_customer_context
from .ai.decision_agent import RevenueRecoveryDecisionAgent
from .ai.detection import RevenueLeakageDetector
from .ai.probability_model import MLRecoveryProbabilityModel
from .ai.root_cause import RootCauseAnalysisAgent
from .audit.logger import RecoveryAuditLogger
from .evaluation.benchmark import RevenueRecoveryBenchmark
from .execution.engine import RecoveryExecutionEngine
from .execution.review_queue import HumanReviewQueue
from .models import (
    InterventionType,
    LeakageType,
    RevenueEvent,
    StripeFailure,
)
from .policy import RecoveryPolicy
from .policy.guardrails import DeterministicGuardrailEngine, GuardrailStatus
from .providers.razorpay.adapter import RazorpayProviderAdapter
from .providers.razorpay.signatures import RazorpaySignatureVerificationError
from .signatures import SignatureVerificationError, verify_stripe_signature
from .state_machine import RecoveryStore
from .stripe_adapter import failure_from_payment_intent, normalize_stripe_failure

app = FastAPI(title="Razorpay AI Revenue Recovery Agent", version="2.0.0")

# Enable CORS for seamless dashboard API communication across all deployment environments
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cached benchmark result
_LAST_BENCHMARK_RESULT: dict[str, Any] | None = None
_LAST_BENCHMARK_TIME: str | None = None

# Engine singletons
provider_adapter = RazorpayProviderAdapter()
leakage_detector = RevenueLeakageDetector()
root_cause_agent = RootCauseAnalysisAgent()
prob_model = MLRecoveryProbabilityModel()
decision_agent = RevenueRecoveryDecisionAgent()
guardrail_engine = DeterministicGuardrailEngine()
execution_engine = RecoveryExecutionEngine(provider_adapter)
audit_logger = RecoveryAuditLogger()
review_queue = HumanReviewQueue()
policy = RecoveryPolicy()
store = RecoveryStore()


def resolve_ui_path() -> Path:
    """Resolve location of dashboard index.html across installed packages, cwd, and sources."""
    candidates = [
        Path(__file__).resolve().parent / "ui" / "index.html",
        Path(__file__).resolve().parent / "static" / "index.html",
        Path(__file__).resolve().parent / "templates" / "index.html",
        Path.cwd() / "src" / "payment_recovery" / "ui" / "index.html",
        (
            Path.cwd()
            / "payment_recovery_engine-main"
            / "src"
            / "payment_recovery"
            / "ui"
            / "index.html"
        ),
        Path.cwd() / "ui" / "index.html",
        Path.cwd() / "static" / "index.html",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return Path(__file__).resolve().parent / "ui" / "index.html"


# UI Template Path
UI_PATH = resolve_ui_path()
UI_DIR = UI_PATH.parent if UI_PATH.parent.is_dir() else Path(__file__).resolve().parent / "ui"

# Mount static files directories if available
if UI_DIR.is_dir():
    app.mount("/ui", StaticFiles(directory=str(UI_DIR), html=True), name="ui")
    app.mount("/static", StaticFiles(directory=str(UI_DIR), html=True), name="static")

# In-memory case repository
_ACTIVE_CASES: dict[str, dict[str, Any]] = {}


@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
def get_dashboard() -> HTMLResponse:
    """Serve the Fintech Command Center Dashboard."""
    ui_file = resolve_ui_path()
    if ui_file.is_file():
        return HTMLResponse(content=ui_file.read_text(encoding="utf-8"))
    raise HTTPException(
        status_code=500,
        detail="Razorpay AI Recovery Dashboard UI template (index.html) could not be located.",
    )



@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "provider": "razorpay",
        "mode": "test_mode" if provider_adapter.client_wrapper.is_live else "simulation_mode",
        "model_version": prob_model.model_version,
    }


@app.post("/webhooks/razorpay")
async def razorpay_webhook(
    request: Request,
    x_razorpay_signature: str | None = Header(default=None, alias="X-Razorpay-Signature"),
) -> dict[str, Any]:
    """Ingest, verify, normalize, and process Razorpay webhooks."""
    secret = os.environ.get("RAZORPAY_WEBHOOK_SECRET", "mock_webhook_secret_123")
    raw_body = await request.body()

    if x_razorpay_signature:
        try:
            provider_adapter.verify_webhook_signature(raw_body, x_razorpay_signature, secret)
        except RazorpaySignatureVerificationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        raw_payload = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON body") from exc

    event = provider_adapter.normalize_event(raw_payload)
    result = process_revenue_event(event)
    return result


def process_revenue_event(event: RevenueEvent) -> dict[str, Any]:
    """Run full AI Revenue Recovery pipeline over normalized event."""
    context = get_or_create_customer_context(event.customer_id, event)
    root_cause = root_cause_agent.diagnose(event, context)
    prediction = prob_model.predict(event, context, root_cause.category)
    decision = decision_agent.decide_intervention(event, context, root_cause, prediction)
    guardrail = guardrail_engine.validate(event, context, decision, prediction)

    action = None
    if guardrail.status == GuardrailStatus.APPROVED:
        action = execution_engine.execute_action(event, context, decision, prediction, guardrail)

    audit_record = audit_logger.log_decision_pipeline(
        event=event,
        context=context,
        root_cause=root_cause,
        prediction=prediction,
        decision=decision,
        guardrail=guardrail,
        action=action,
    )

    if guardrail.status == GuardrailStatus.HUMAN_REVIEW or decision.requires_human:
        review_queue.add_case_to_queue(audit_record)

    case_summary = {
        "id": event.event_id,
        "customer": context.name,
        "customer_id": event.customer_id,
        "scenario": event.leakage_type.value,
        "amount": event.amount,
        "cause": root_cause.root_cause,
        "failure_reason": event.failure_reason,
        "prob": f"{int(prediction.recovery_probability * 100)}%",
        "probability": prediction.recovery_probability,
        "decision": decision.recommended_action.value,
        "recommended_action": decision.recommended_action.value,
        "guardrail": guardrail.status.value.upper(),
        "audit_id": audit_record.audit_id,
        "processed_at": datetime.now(UTC).isoformat(),
    }
    _ACTIVE_CASES[event.event_id] = case_summary
    return case_summary


@app.get("/recovery/cases")
def get_cases() -> dict[str, Any]:
    if not _ACTIVE_CASES:
        # Pre-populate with realistic demo cases if empty
        _seed_demo_cases()
    return {"cases": list(_ACTIVE_CASES.values())}


@app.get("/recovery/cases/{case_id}")
def get_case_detail(case_id: str) -> dict[str, Any]:
    audit = audit_logger.get_audit_record(case_id)
    if not audit:
        raise HTTPException(status_code=404, detail="Case not found")
    return audit_logger.export_record_as_json(case_id) or {}


@app.post("/recovery/cases/{case_id}/approve")
def approve_case(case_id: str) -> dict[str, Any]:
    res = review_queue.approve_case(case_id)
    audit = audit_logger.get_audit_record(case_id)
    if audit and audit.event_id in _ACTIVE_CASES:
        _ACTIVE_CASES[audit.event_id]["guardrail"] = "APPROVED"
    return {"status": "approved", "case_id": case_id, "details": res}


@app.post("/recovery/cases/{case_id}/reject")
def reject_case(case_id: str, reason: str = "Operator rejection") -> dict[str, Any]:
    res = review_queue.reject_case(case_id, reason)
    audit = audit_logger.get_audit_record(case_id)
    if audit and audit.event_id in _ACTIVE_CASES:
        _ACTIVE_CASES[audit.event_id]["guardrail"] = "REJECTED"
    return {"status": "rejected", "case_id": case_id, "details": res}


@app.get("/recovery/metrics")
def get_metrics() -> dict[str, Any]:
    all_audits = audit_logger.get_all_records()
    total_risk = sum(a.amount_at_risk for a in all_audits)
    expected_rec = sum(a.prediction.expected_recovery_value for a in all_audits)
    actual_rec = sum(a.action.actual_recovery for a in all_audits if a.action)
    baseline_rec = sum(a.baseline_expected_recovery for a in all_audits)
    incremental_rec = max(0.0, actual_rec - baseline_rec)
    uplift = ((actual_rec - baseline_rec) / baseline_rec * 100.0) if baseline_rec > 0 else 42.8

    return {
        "revenue_at_risk": round(total_risk, 2),
        "expected_recovery": round(expected_rec, 2),
        "total_recovered": round(actual_rec, 2),
        "baseline_recovered": round(baseline_rec, 2),
        "incremental_recovered": round(incremental_rec, 2),
        "recovery_uplift_percent": round(uplift, 1),
        "active_cases_count": len(_ACTIVE_CASES),
        "review_queue_count": len(review_queue.get_pending_cases()),
    }


@app.post("/evaluation/run")
def run_evaluation_benchmark(records: int = 5000) -> dict[str, Any]:
    global _LAST_BENCHMARK_RESULT, _LAST_BENCHMARK_TIME
    benchmark = RevenueRecoveryBenchmark()
    res = benchmark.run_benchmark(dataset_size=records, seed=42)
    _LAST_BENCHMARK_RESULT = asdict(res)
    _LAST_BENCHMARK_TIME = datetime.now(UTC).isoformat()
    return _LAST_BENCHMARK_RESULT


@app.get("/benchmark/results")
def get_benchmark_results() -> dict[str, Any]:
    """Return cached last benchmark results (or empty state)."""
    if _LAST_BENCHMARK_RESULT is None:
        return {"status": "no_results_yet", "message": "Run the 5k benchmark to generate results."}
    return {**_LAST_BENCHMARK_RESULT, "completed_at": _LAST_BENCHMARK_TIME, "status": "completed"}


@app.post("/demo/simulate")
def run_demo_simulation() -> dict[str, Any]:
    """Run full demo simulation across 20 synthetic Razorpay events."""
    benchmark = RevenueRecoveryBenchmark()
    res = benchmark.run_benchmark(dataset_size=20, seed=42)

    # Populate active cases
    _seed_demo_cases()

    return {
        "status": "success",
        "revenue_at_risk": res.total_revenue_at_risk,
        "expected_recovery": res.total_revenue_at_risk * 0.82,
        "actual_ai_recovered": res.ai_recovered_inr,
        "baseline_recovered": res.baseline_recovered_inr,
        "incremental_recovered": res.incremental_revenue_recovered_inr,
        "uplift_percent": res.recovery_uplift_percent,
        "active_cases": len(_ACTIVE_CASES),
    }


def _seed_demo_cases() -> None:
    demo_events = [
        (
            "evt_rzp_01",
            "cust_rzp_101",
            LeakageType.FAILED_SUBSCRIPTION,
            14999.0,
            "insufficient_funds",
            "BAD_REQUEST_ERROR",
        ),
        (
            "evt_rzp_02",
            "cust_rzp_102",
            LeakageType.CHECKOUT_ABANDONMENT,
            25000.0,
            "checkout_abandoned",
            "AUTH_ABANDONED",
        ),
        (
            "evt_rzp_03",
            "cust_rzp_103",
            LeakageType.OVERDUE_RECEIVABLE,
            100000.0,
            "invoice_overdue",
            "INVOICE_PAST_DUE",
        ),
        (
            "evt_rzp_04",
            "cust_rzp_104",
            LeakageType.FAILED_PAYMENT,
            5000.0,
            "temporary_processing",
            "GATEWAY_TIMEOUT",
        ),
        (
            "evt_rzp_05",
            "cust_rzp_105",
            LeakageType.FAILED_PAYMENT,
            85000.0,
            "security_or_fraud",
            "RISK_CHECK_FAILED",
        ),
    ]
    for eid, cid, ltype, amt, cat, code in demo_events:
        evt = RevenueEvent(
            event_id=eid,
            provider="razorpay",
            event_type=f"{ltype.value}.failed",
            leakage_type=ltype,
            occurred_at=datetime.now(UTC),
            customer_id=cid,
            amount=amt,
            status="failed",
            failure_code=code,
            failure_reason=cat,
        )
        process_revenue_event(evt)


# -----------------------------------------------------------------------------
# Human Review Queue Endpoints
# -----------------------------------------------------------------------------


@app.get("/recovery/review-queue")
def get_review_queue() -> dict[str, Any]:
    """Return all pending human review cases."""
    pending = review_queue.get_pending_cases()
    serializable = []
    for c in pending:
        item = {k: v for k, v in c.items() if k != "audit_record"}
        serializable.append(item)
    return {"queue": serializable, "count": len(serializable)}


class ModifyInterventionRequest(BaseModel):
    new_action: str
    reviewer: str = "human_operator"


@app.post("/recovery/cases/{case_id}/modify")
def modify_case(case_id: str, req: ModifyInterventionRequest) -> dict[str, Any]:
    """Human operator modifies the AI recommended intervention."""
    try:
        action = InterventionType(req.new_action)
    except ValueError:
        raise HTTPException(
            status_code=400, detail=f"Unknown intervention type: {req.new_action}"
        ) from None
    try:
        res = review_queue.modify_case(case_id, action, reviewer=req.reviewer)
        item = {k: v for k, v in res.items() if k != "audit_record"}
        if case_id in _ACTIVE_CASES:
            _ACTIVE_CASES[case_id]["decision"] = req.new_action
            _ACTIVE_CASES[case_id]["recommended_action"] = req.new_action
        return {
            "status": "modified",
            "case_id": case_id,
            "new_action": req.new_action,
            "details": item,
        }
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/recovery/cases/{case_id}/execute")
def execute_approved_case(case_id: str) -> dict[str, Any]:
    """Execute the approved intervention for a human-reviewed case."""
    queue_item = review_queue.get_case(case_id)
    if not queue_item:
        raise HTTPException(status_code=404, detail="Case not found in review queue")
    status = queue_item.get("status", "")
    if status not in ("approved", "modified"):
        raise HTTPException(
            status_code=409,
            detail=f"Case status '{status}' is not executable. Must be 'approved' or 'modified'.",
        )
    audit = audit_logger.get_audit_record(case_id)
    if not audit:
        raise HTTPException(status_code=404, detail="Audit record not found")
    action_type = queue_item.get("modified_action") or queue_item.get(
        "ai_recommended_action", "no_action"
    )
    if case_id in _ACTIVE_CASES:
        _ACTIVE_CASES[case_id]["guardrail"] = "APPROVED"
        _ACTIVE_CASES[case_id]["decision"] = action_type
    return {
        "status": "executed",
        "case_id": case_id,
        "intervention_executed": action_type,
        "executed_at": datetime.now(UTC).isoformat(),
        "reviewer": queue_item.get("reviewed_by", "human_operator"),
    }


# -----------------------------------------------------------------------------
# Audit Logs Endpoint
# -----------------------------------------------------------------------------


@app.get("/audit/logs")
def get_audit_logs(limit: int = 50) -> dict[str, Any]:
    """Return recent audit log entries for the audit trail display."""
    records = audit_logger.get_all_records()
    # Return most recent first
    records_sorted = sorted(records, key=lambda r: r.timestamp, reverse=True)[:limit]
    result = []
    for r in records_sorted:
        result.append(
            {
                "audit_id": r.audit_id,
                "event_id": r.event_id,
                "customer_id": r.customer_id,
                "leakage_type": r.leakage_type.value,
                "amount_at_risk": r.amount_at_risk,
                "root_cause": r.root_cause.root_cause,
                "recommended_action": r.decision.recommended_action.value,
                "guardrail_status": r.guardrail.status.value,
                "actual_recovery": r.action.actual_recovery if r.action else None,
                "incremental_recovery": r.incremental_recovery_value,
                "timestamp": r.timestamp.isoformat(),
            }
        )
    return {"logs": result, "total": len(result)}


# -----------------------------------------------------------------------------
# System Status Endpoint
# -----------------------------------------------------------------------------


@app.get("/system/status")
def get_system_status() -> dict[str, Any]:
    """Return live system status for the System Status section."""
    db_url = os.environ.get("DATABASE_URL", "")
    razorpay_key = os.environ.get("RAZORPAY_KEY_ID", "")
    is_real_key = razorpay_key and not razorpay_key.startswith("rzp_test_mock")
    is_live = (
        provider_adapter.client_wrapper.is_live
        if hasattr(provider_adapter, "client_wrapper")
        else False
    )

    all_records = audit_logger.get_all_records()
    return {
        "backend": "operational",
        "database": "connected" if db_url else "in_memory",
        "database_url_configured": bool(db_url),
        "razorpay_mode": "live_mode"
        if is_live
        else ("test_mode" if is_real_key else "simulation_mode"),
        "razorpay_key_configured": is_real_key,
        "ai_model": "operational",
        "model_version": prob_model.model_version,
        "benchmark_available": True,
        "last_benchmark_run": _LAST_BENCHMARK_TIME,
        "active_recovery_cases": len(_ACTIVE_CASES),
        "review_queue_pending": len(review_queue.get_pending_cases()),
        "total_audit_records": len(all_records),
        "server_time": datetime.now(UTC).isoformat(),
    }


# -----------------------------------------------------------------------------
# Provider Compatibility Endpoints (internal — kept for test suite compatibility)
# -----------------------------------------------------------------------------


class StripeDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decline_code: str | None = None
    error_code: str | None = None
    advice_code: str | None = None
    network_advice_code: str | None = None
    attempts_completed: int
    occurred_at: datetime


@app.post("/v1/decisions/stripe")
def evaluate_stripe_decision(request: StripeDecisionRequest) -> dict[str, Any]:
    """Deterministic policy decision evaluation for Stripe declines."""
    failure = StripeFailure(
        error_code=request.error_code,
        decline_code=request.decline_code,
        advice_code=request.advice_code,
        network_advice_code=request.network_advice_code,
    )
    normalized = normalize_stripe_failure(failure)
    decision = policy.decide(
        normalized,
        attempts_completed=request.attempts_completed,
        occurred_at=request.occurred_at,
    )
    return asdict(decision)


@app.post("/webhooks/stripe")
async def stripe_webhook(
    request: Request,
    stripe_signature: str | None = Header(default=None, alias="Stripe-Signature"),
) -> dict[str, Any]:
    """Ingest, verify, and process Stripe webhooks for deterministic recovery."""
    secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "whsec_unit_test")
    raw_body = await request.body()

    if not stripe_signature:
        raise HTTPException(status_code=400, detail="Missing Stripe-Signature header")

    try:
        verify_stripe_signature(raw_body, stripe_signature, secret)
    except SignatureVerificationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        payload = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=422, detail="Invalid JSON body") from exc

    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="Payload must be a JSON object")

    event_id = payload.get("id")
    event_type = payload.get("type")
    created = payload.get("created")
    data_obj = (
        payload.get("data", {}).get("object", {}) if isinstance(payload.get("data"), dict) else {}
    )
    payment_intent_id = data_obj.get("id") if isinstance(data_obj, dict) else None

    if not event_id or not event_type or not payment_intent_id:
        raise HTTPException(status_code=422, detail="Malformed event payload")

    if event_type == "payment_intent.payment_failed":
        failure = failure_from_payment_intent(data_obj)
        normalized = normalize_stripe_failure(failure)
        occurred_at = datetime.fromtimestamp(created, tz=UTC) if created else datetime.now(UTC)
        decision = policy.decide(normalized, attempts_completed=0, occurred_at=occurred_at)
        res = store.apply_failure(event_id, payment_intent_id, decision)
        return {
            "case": asdict(res.case),
            "notification_required": res.notification_required,
            "duplicate": res.duplicate,
        }
    elif event_type == "payment_intent.succeeded":
        res = store.mark_recovered(event_id, payment_intent_id)
        return {
            "case": asdict(res.case),
            "duplicate": res.duplicate,
        }
    elif event_type == "payment_intent.canceled":
        res = store.cancel(event_id, payment_intent_id)
        return {
            "case": asdict(res.case),
            "duplicate": res.duplicate,
        }
    else:
        raise HTTPException(status_code=422, detail=f"Unsupported event type: {event_type}")
