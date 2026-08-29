# Architecture

## Ownership boundaries

The Python package owns deterministic behavior: Stripe normalization, policy, signatures, and state transitions. PostgreSQL owns durable uniqueness, leases, retry attempts, notification claims, and optimistic terminal updates. n8n owns schedules, managed credentials, provider calls, email delivery, and operational reporting.

This split prevents a visual workflow edit from silently changing financial policy.

## State and idempotency

```text
payment_failed → pending | action_required | manual_review | exhausted
pending → attempting → pending | recovered | exhausted | manual_review
any nonterminal → recovered | cancelled
recovered/cancelled → terminal
```

The provider event ID deduplicates intake. `(case, attempt_number)` plus the Stripe idempotency key deduplicates charges. `(case, notification_kind)` deduplicates messages. `version` prevents stale terminal writes. `claim_due_retries` uses row locks with `SKIP LOCKED` so concurrent workers do not claim the same case.

## Deployment gap

The pure state machine uses an in-memory reference store to keep logic fast and independently testable. It is not the production repository. A deployment must implement the same transition contract in a transaction that writes `webhook_events`, `recovery_cases`, and any outbox record before acknowledging the provider. The included SQL establishes the constraints and worker functions; the durable Python repository/outbox adapter remains deliberate technical debt.

## Why n8n remains

n8n is well suited to managed credentials, schedules, email, and operator-visible executions. It is not the authority for decline semantics, retry budgets, or schedule math. The workflow artifacts therefore consume policy decisions and use database claims instead of embedding those rules.

## Failure handling

- Invalid signatures and malformed events fail before policy.
- Unknown provider codes fail safe to manual review.
- Security-sensitive failures do not auto-retry or generate customer-facing fraud detail.
- Provider state is rechecked immediately before confirmation.
- Terminal states clear `next_retry_at`.
- Duplicate events, attempts, and notifications are rejected by both code and database constraints.
