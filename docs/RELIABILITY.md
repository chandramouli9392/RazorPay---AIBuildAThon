# Reliability and Failure Modes

Payment recovery systems touch real customer billing. They must fail safely, avoid duplicate actions, and preserve a complete audit trail.

## Duplicate webhook delivery

Stripe can redeliver events. Persist the provider event ID and make processing idempotent.

**Acceptance condition:** replaying the same event produces no duplicate retry, email, or database transition.

## Invalid webhook authenticity

Verify the provider signature before accepting an event. Reject malformed or unverifiable requests before business logic runs.

## Retry races

Two workers or workflow executions can attempt to schedule/process the same retry.

**Controls:** atomic state transitions, unique attempt identifiers, transactional updates, and explicit lock/version semantics where needed.

## Retry after recovery

A scheduled retry may become stale because the invoice was paid, subscription cancelled, or payment method changed.

**Control:** re-check current billing state immediately before attempting recovery.

## Retry-budget exhaustion

Every policy needs a hard stop. Attempts must be counted durably and compared against the configured policy.

## Decline-code misclassification

Provider decline codes and semantics can change.

**Control:** isolate provider-code mapping from the core policy engine and test mappings separately.

## Security/fraud failures

Do not automatically retry events that require security/manual review unless provider guidance and the client's policy explicitly allow it.

## Notification duplication

Customers should not receive multiple identical emails because of workflow replay.

**Control:** store notification state/idempotency keys and test replay behavior.

## Provider/API outages

Use bounded retries with backoff and durable failed-event handling. A provider outage should not silently drop recovery work.

## Scheduling drift

Retry timestamps must be explicit, timezone-safe, and persisted. Do not rely solely on in-memory workflow state.

## Implemented state-machine contract

A stronger implementation should model recovery state explicitly, for example:

```text
RECEIVED
  ↓
CLASSIFIED
  ↓
SCHEDULED ──→ MANUAL_REVIEW
  ↓
ATTEMPTING
  ├──→ RECOVERED
  ├──→ RESCHEDULED
  └──→ EXHAUSTED
```

The Python reference store validates these transitions, and PostgreSQL provides durable uniqueness and optimistic terminal updates. A durable Python repository/outbox adapter is still required before production deployment.

## Observability target

Track at least:
- failures received by category;
- active retry queue;
- attempts by policy;
- recovery rate by category;
- amount at risk;
- duplicate event count;
- notification count;
- provider/API errors;
- exhausted cases;
- manual-review backlog;
- workflow latency.

## Test acceptance set

Before production labeling, automated tests should cover:
- valid/invalid webhook signatures;
- duplicate webhooks;
- all major policy categories;
- retry schedule calculation;
- retry exhaustion;
- recovery before scheduled retry;
- cancellation before scheduled retry;
- notification idempotency;
- provider failure/retry behavior;
- concurrent processing;
- malformed payloads.

The core classification and policy logic should be independently testable outside n8n.
