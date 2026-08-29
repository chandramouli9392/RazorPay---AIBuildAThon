# Evidence and Claim Policy

This repository is a public reference implementation for payment-failure recovery. Claims should be traceable to code, automated tests, reproducible simulations, or production evidence.

## Evidence classes

| Label | Meaning |
|---|---|
| **Implemented** | Capability exists in repository artifacts |
| **Tested** | Covered by executable automated tests |
| **Synthetic / Demonstration** | Proven only with test fixtures or generated events |
| **Modeled Outcome** | Business impact derived from assumptions |
| **Production** | Verified live-system evidence |
| **Client Outcome** | Real customer result with evidence/permission |

## Current repository status

**Reference Implementation / Validation Candidate**

### Implemented
- deterministic Python normalization, policy, signature, and state-machine modules;
- executable Python, service, concurrency, artifact, and PostgreSQL tests;
- atomic PostgreSQL retry claims, idempotency ledgers, and terminal version checks;
- n8n orchestration artifacts with named credentials and no embedded business policy;
- runtime email templates and synthetic database fixtures;
- Python 3.11, Ruff, GitHub Actions, Docker, and Docker Compose configuration.

### Executed in the engineering pass

- complete automated suite in Python 3.11;
- schema and integration assertions on PostgreSQL 16;
- static import/contract validation for all five n8n JSON files;
- secret-pattern and generated-artifact checks.

This is test evidence, not production evidence.

### Not established by this repository alone
- 28–35% recovery rate;
- 3× recovery improvement;
- $12K–15K monthly recovered revenue;
- 96% reduction in manual effort;
- production response-time or availability claims.

Any future recovery benchmark should state:
- number of simulated failures;
- decline-code distribution;
- retry policy;
- control/baseline policy;
- recovered vs unrecovered cases;
- duplicate/replay scenarios;
- notification count;
- time horizon;
- whether recovery was simulated or observed in production.

Do not convert modeled or synthetic outcomes into client-result language.
