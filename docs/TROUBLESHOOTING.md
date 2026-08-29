# Troubleshooting

## Webhook returns `signature mismatch`

- Confirm the endpoint's exact `whsec_...` secret is configured.
- Pass the untouched request bytes. Parsing and re-serializing JSON changes the signed payload.
- Check whether the request came through a proxy that rewrites the body.
- During secret rotation, Stripe can include multiple `v1` values; the verifier accepts any valid one.

Never disable verification to make a fixture pass. Generate a valid test signature or use Stripe CLI forwarding.

## `signature timestamp outside tolerance`

Check host time synchronization and proxy/queue delay. Both old and implausibly future timestamps fail. Do not permanently widen the tolerance to hide clock drift.

## A webhook was delivered twice

This is expected provider behavior. Look up `(provider, provider_event_id)` in `webhook_events`. A replay should not add a recovery transition, retry attempt, or notification. If it does, stop the worker and inspect database constraints before resuming.

## A customer received duplicate email

Query `notification_deliveries` by recovery case and kind. The unique constraint is the final deduplication boundary. Ensure the email node runs only after `Claim Notification Once` returns a row.

## A retry ran after payment or cancellation

The worker must re-read the PaymentIntent immediately before confirmation and close stale work through `mark_recovery_terminal`. Check the case version, Stripe response, and worker execution. Do not manually reset a terminal case to pending.

## Cases are stuck in `attempting`

Inspect `lease_owner`, `lease_expires_at`, and the failed n8n execution. An expired `attempting` lease is eligible for atomic reclaim; the worker then rechecks Stripe state and reuses the deterministic provider idempotency key. If a case remains stuck after lease expiry, verify its due time and retry budget rather than updating rows blindly.

## `do_not_honor` appears as fraud

That mapping is incorrect. The current adapter treats it as a conservative hard decline requiring customer/issuer action or review. Only explicit security-sensitive codes enter `security_or_fraud`.

## PostgreSQL schema fails

Use PostgreSQL 16 with permission to create `pgcrypto`. Run `database/schema.sql` against an empty test database first. The schema is transactional and safe to rerun, but policy migrations in a live system require a migration tool and backup plan.

## n8n import succeeds but execution fails

Verify node availability/version, attach every named credential, configure environment variables, and confirm internal webhook authentication. Static JSON validation proves structure and absence of embedded secrets; it does not prove a specific hosted n8n environment.

## Test-mode decline behaves differently

Use current Stripe test PaymentMethods and inspect both top-level `code` and `decline_code`. Most issuer-decline test cards cannot be attached to a Customer; use the documented attach-then-decline PaymentMethod for that scenario. Do not load-test Stripe test mode.
