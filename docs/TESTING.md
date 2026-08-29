# Testing

## Automated acceptance

```bash
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/pytest
```

Without `DATABASE_URL`, the PostgreSQL integration test skips. Docker Compose supplies it and is the reproducible full command:

```bash
docker compose up --build --abort-on-container-exit --exit-code-from tests
```

Coverage includes signatures, malformed input, decline normalization, schedules, exhaustion, duplicate and concurrent events, notification deduplication, success/cancellation terminal behavior, workflow contracts, template hygiene, atomic PostgreSQL claims, duplicate attempt keys, and stale-version rejection.

## Stripe test-mode acceptance

Use Stripe's current [test PaymentMethods](https://docs.stripe.com/testing?testing-method=payment-methods), not copied live cards:

| Scenario | Test PaymentMethod | Expected policy |
|---|---|---|
| Generic issuer decline | `pm_card_visa_chargeDeclined` | hard decline; no unattended retry |
| Insufficient funds | `pm_card_visa_chargeDeclinedInsufficientFunds` | bounded scheduled retries |
| Expired card | `pm_card_chargeDeclinedExpiredCard` | update method; no blind retry |
| Attach succeeds, later charge declines | `pm_card_chargeCustomerFail` | suitable for Customer/subscription testing |

Stripe test mode is for functional testing, not load testing. Use Stripe CLI or a Dashboard test endpoint so the signing secret and payload are genuine. Do not disable signature verification or use a fake signature header.

## Required manual acceptance before activation

1. Import all workflow JSON files into the target n8n version while inactive.
2. Confirm public requests cannot reach internal n8n webhooks.
3. Send a signed test failure twice and prove one event, one state transition, and one notification claim.
4. Run two retry workers concurrently and prove one database claim/provider idempotency key.
5. Mark a PaymentIntent successful or cancelled before its due retry and prove no confirmation occurs.
6. Exercise SMTP failure and provider timeout paths; verify the work remains inspectable and recoverable.

No benchmark or recovery-rate result is produced by this suite. It validates deterministic safety behavior.
