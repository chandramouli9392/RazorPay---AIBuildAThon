# Configuration

## Runtime variables

Copy `.env.example` into the secret manager for the target environment. Do not commit the populated file.

| Variable | Required by | Purpose |
|---|---|---|
| `STRIPE_WEBHOOK_SECRET` | Python service | Endpoint-specific `whsec_...` used against exact raw request bytes |
| `DATABASE_URL` | persistence adapter/tests | PostgreSQL connection string; use TLS in hosted environments |
| `RECOVERY_ENGINE_INTERNAL_TOKEN` | service/n8n | Authenticates internal orchestration calls |
| `RECOVERY_ENGINE_URL` | n8n retry worker | Base URL for deterministic policy decisions |
| `RECOVERY_FROM_EMAIL` | n8n email | Verified sender address |
| `RECOVERY_REPORT_EMAIL` | n8n report | Internal operational report recipient |
| `N8N_INTERNAL_WEBHOOK_URL` | deployment adapter | Protected internal workflow endpoint |
| `N8N_POLICY_DECISION_URL` | n8n intake | Protected persistence workflow endpoint |

Use separate Stripe keys and webhook secrets per environment. A Stripe CLI secret is not interchangeable with a Dashboard endpoint secret.

## Credential boundaries

- Stripe secret keys, SMTP credentials, and PostgreSQL passwords live in the platform secret store or n8n Credentials.
- Workflow exports contain credential names only. Never paste secret values into JSON nodes.
- Only the Python endpoint receives public Stripe webhooks. n8n intake webhooks are internal and header-authenticated.
- The database role used by the worker should be limited to the recovery tables/functions it requires.

## Policy configuration

Policy defaults are versioned in `src/payment_recovery/policy.py`. A change to timing, category mapping, or attempt budgets requires:

1. a new policy version;
2. unit tests for each changed category and boundary;
3. product/legal review of customer messaging and retry consent;
4. an explicit decision about active cases—retain their old policy or migrate them audibly.

Do not edit retry timing inside n8n. That would create two competing sources of truth.

## n8n import

Import all five JSON files while they are inactive, attach named credentials, set the runtime variables, and inspect expressions before activation. The intended order is verified intake, persistence, notification, retry worker, then report. Keep public access disabled for internal webhooks.

## Production gate

Before live credentials are allowed, verify durable service-to-PostgreSQL event processing, authenticated n8n import/execution, provider idempotency keys, lease recovery, alerting, data retention, customer-consent wording, and a rollback/runbook. Passing this repository's tests does not satisfy those environment-specific controls.
