# Contributing

Changes to failure mapping, retry budgets, schedules, state transitions, or customer messaging require executable tests and an evidence note. Keep provider adapters separate from the deterministic policy core, and keep financial policy out of n8n code nodes.

Before opening a pull request, run:

```bash
ruff check .
ruff format --check .
pytest
```

Use Docker Compose when changing PostgreSQL behavior. Never commit populated environment files, credentials, real customer/payment data, or unsupported outcome claims. New billing providers should include official-semantics references, malformed-input cases, idempotency tests, and a clear manual-review policy.
