# Installation

## Local Python 3.11

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install '.[dev]'
.venv/bin/pytest
```

Run the API only after setting a test endpoint secret:

```bash
export STRIPE_WEBHOOK_SECRET=whsec_from_test_endpoint
.venv/bin/python -m payment_recovery
```

The health endpoint is `GET /health`; Stripe webhooks enter at `POST /webhooks/stripe`.

## Docker Compose

```bash
docker compose up --build --abort-on-container-exit --exit-code-from tests
```

This starts a disposable PostgreSQL 16 database and runs the full suite. It does not contact Stripe or send email.

## Database

Apply `database/schema.sql` using a migration role. `database/sample-data.sql` is synthetic, idempotent fixture data and must not be loaded into a production billing database.

## n8n

Import the five workflows inactive. Attach these named credentials:

- `Recovery Engine Internal Auth` (Header Auth)
- `Payment Recovery PostgreSQL` (PostgreSQL)
- `Stripe Test Mode` (Stripe API)
- `Payment Recovery SMTP` (SMTP)

Configure the variables in [`CONFIGURATION.md`](./CONFIGURATION.md), inspect every node, and perform authenticated test-mode acceptance before activation. The Python service—not n8n—must be the public Stripe webhook boundary because verification requires exact raw bytes.

## Production deployment

This repository is a validated reference implementation, not a turnkey production service. A production release additionally requires a durable Python PostgreSQL/outbox adapter, secret management, TLS, authenticated internal routing, monitoring, lease recovery, backups, retention controls, customer-policy review, and a rollback exercise.
