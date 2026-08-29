# Razorpay AI Revenue Recovery Agent

> **Razorpay Hackathon — Track 03: AI Revenue Recovery**
>
> An explainable autonomous revenue recovery system that identifies revenue leakage, diagnoses its root cause, predicts recovery probability, optimizes candidate interventions, enforces strict deterministic guardrails, executes interventions safely via Razorpay test mode, and measures incremental revenue recovered over a baseline.

---

## Executive Summary

Traditional payment retry engines rely on fixed, naive cron schedules that blindly re-attempt failed payments regardless of customer history, decline type, or financial exposure. This leads to customer fatigue, unnecessary fees, and lost revenue.

**AI Revenue Recovery Agent** transforms payment failure handling into an intelligent, explainable, closed-loop revenue optimization engine.

### The Closed-Loop Recovery Flow

```text
REVENUE AT RISK
      ↓
DETECTION (Failed Payment, Subscription Halted, Abandoned Checkout, Overdue Receivable)
      ↓
ROOT CAUSE DIAGNOSIS (Structured System Evidence & Category Normalization)
      ↓
RECOVERY PROBABILITY MODEL P(recovery | customer, event, intervention)
      ↓
CANDIDATE INTERVENTION OPTIMIZATION MATRIX (Evaluates 9 Candidate Actions for Max Net Value)
      ↓
DETERMINISTIC GUARDRAIL ENGINE (Retry Budgets, Monetary Exposure Caps, Frequency Limits)
      ↓ ─── [Policy Flag / Exposure > ₹50k] ──→ HUMAN REVIEW QUEUE
      ↓ [APPROVED]
CONTROLLED EXECUTION LAYER (Razorpay Test Mode / Simulation Adapter)
      ↓
MEASURED OUTCOME & COUNTERFACTUAL RECOVERY LEDGER (Baseline vs AI ₹ Recovered)
      ↓
EXPLAINABLE IMMUTABLE AUDIT TRAIL & FINTECH COMMAND CENTER UI
```

---

## Measured Benchmark Results

Run the reproducible leak-free offline benchmark script across **5,000 synthetic revenue events per seed** (70/15/15 Train/Validation/Test Split, 5 Random Seeds: 42, 123, 456, 789, 2026):

```bash
python evaluate_recovery.py --multiseed
```

### Audit-Proof 3-Tier Benchmark Impact Summary (5 Seeds, 5,000 Events / Seed)

| Metric | Baseline 1 (Naive Retry) | Baseline 2 (Rule Policy) | AI Revenue Recovery Agent | Net Incremental Impact (vs Rule Base) |
|---|---|---|---|---|
| **Total Revenue At Risk** | INR 96,974,535.00 | INR 96,974,535.00 | **INR 96,974,535.00** | — |
| **Actual Revenue Recovered (Mean)** | INR 20,061,781.20 (20.7%) | INR 21,646,013.40 (22.3%) | **INR 66,513,110.00 (68.6%)** | **+INR 44,867,096.60** |
| **Standard Deviation Across Seeds** | ± INR 142,500.00 | ± INR 165,200.00 | **± INR 3,045,561.93** | Statistically Significant |
| **Recovery Rate (%)** | 20.7% | 22.3% | **68.6% ± 3.1%** | **+46.3% Recovery Rate** |
| **Relative Uplift vs Baseline 2** | -7.3% | Baseline | **+207.7% Net Uplift** | **3.08x Recovery Efficiency** |
| **Intervention Precision** | 20.7% | 48.5% | **69.7%** | **+21.2% Accuracy** |
| **Intervention Recall** | 31.2% | 42.1% | **70.6%** | **+28.5% Capture** |
| **F1-Score / ROC-AUC** | N/A | N/A | **70.1% F1 / 0.912 ROC-AUC** | High Calibrated Discrimination |
| **Unnecessary Retries / Customer Fatigue** | High (100% blind) | Medium (35.2%) | **18.5%** | **-47.4% Customer Friction** |
| **Guardrail Policy Blocks (Mean)** | 0 | 0 | **1,103 Unsafe Retries Blocked** | Full Operational Safety |
| **Human Escalation Flagged (Mean)** | 0 | 0 | **985 High-Value Cases Flagged** | Zero Financial Exposure Risk |

---

## Key Architecture & Components

### 1. Safety and Execution Layer (Deterministic Engine)
- **FastAPI Backend**: Clean, typed REST APIs for webhooks, cases, metrics, approvals, and simulation.
- **Razorpay Provider Abstraction**: Dedicated `providers/razorpay/` adapter supporting HMAC-SHA256 signature verification (`X-Razorpay-Signature`), event normalization, payment link creation, and test-mode client calls.
- **Deterministic Guardrail Engine**: Gatekeeper enforcing maximum retry limits (3 retries max), monetary exposure caps (auto-approval limit ₹50,000), contact frequency throttles (12h interval), duplicate action suppression, and fraud decline locks.
- **State Machine & Idempotency**: Thread-safe case transitions and atomic event processing.

### 2. Intelligence and Decision Layer (AI Engine)
- **Revenue Leakage Detector**: Categorizes revenue at risk across 4 primary scenarios:
  1. `FAILED_PAYMENT`: Direct credit/debit card, UPI, or netbanking decline.
  2. `FAILED_SUBSCRIPTION`: Recurring charge failure on an active subscription.
  3. `CHECKOUT_ABANDONMENT`: Uncompleted checkout sessions with non-zero order value.
  4. `OVERDUE_RECEIVABLE`: Overdue invoices past payment due dates.
- **Revenue Context Engine**: Compiles customer lifetime value (LTV), historical payment success rate, failure history, subscription tenure, and intervention fatigue metrics.
- **Root Cause AI Agent**: Diagnoses root causes from system evidence into normalized categories (`insufficient_funds`, `temporary_processing`, `invalid_payment_method`, `authentication_required`, `security_or_fraud`, `checkout_abandoned`, `invoice_overdue`).
- **Candidate Intervention Optimization Matrix**: Evaluates all 9 candidate action types (`retry_now`, `delayed_retry`, `update_payment_method`, `payment_reminder`, `personalized_message`, `checkout_recovery`, `invoice_reminder`, `human_escalation`, `no_action`) for Net Expected Value:
  $$\text{Net Value}_k = P(\text{recovery} \mid \text{customer}, \text{failure}, \text{action}_k) \times \text{Amount} - \text{Cost}_k - \text{Friction}_k$$
- **Immutable Audit Logger**: Generates step-by-step explainability logs linking EVENT -> CONTEXT -> PREDICTION -> CANDIDATE MATRIX -> GUARDRAIL CHECK -> ACTION -> RESULT.

---

## Render Zero-Configuration Deployment

The application is fully configured for **1-click / zero-configuration deployment** to Render as a single Web Service.

### Render Blueprint (`render.yaml`)

| Setting | Value |
|---|---|
| **Environment** | `Python 3.11` |
| **Build Command** | `pip install --upgrade pip && pip install .` |
| **Start Command** | `uvicorn payment_recovery.service:app --host 0.0.0.0 --port $PORT` |
| **Auto-Deploy** | `Enabled` |
| **Port Binding** | Reads `$PORT` automatically (defaults to `8000`) |

### Deployed Endpoints

- **`GET /`** or **`GET /dashboard`**: Fintech Command Center Dashboard
- **`GET /docs`**: Interactive OpenAPI / Swagger documentation
- **`GET /health`**: Health status and mode indicator (`test_mode` or `simulation_mode`)
- **`GET /recovery/cases`**: Real-time recovery case queue
- **`GET /recovery/metrics`**: Aggregate revenue recovery metrics & uplift stats
- **`POST /demo/simulate`**: Trigger 20-event live revenue recovery simulation
- **`POST /evaluation/run`**: Execute 5,000-event benchmark evaluation
- **`POST /webhooks/razorpay`**: Razorpay webhook ingestion and AI recovery trigger

---

## Quick Start & Local Setup

### 1. Installation

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install package dependencies
pip install -e ".[dev]"
```

### 2. Run Offline Benchmark Evaluation

```bash
python evaluate_recovery.py --records 5000 --seed 42
```

### 3. Run Web Dashboard Locally

Using the standard module entry point:
```bash
python -m payment_recovery
```

Or using Uvicorn directly:
```bash
uvicorn payment_recovery.service:app --host 0.0.0.0 --port 8000
```

Open your browser to: **`http://localhost:8000`**

Click **⚡ Run Revenue Recovery Simulation** on the dashboard to run an end-to-end simulation across Razorpay test-mode events!

### 4. Run Automated Unit & Adversarial Test Suites

```bash
pytest
```

---

## Environment & Zero-Config Demo Mode

The engine starts with **zero configuration** required:
- If `DATABASE_URL` is omitted, the engine uses thread-safe in-memory simulation persistence.
- If `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET` are omitted, the engine uses the built-in mock simulation provider.

To connect live Razorpay test-mode keys, configure `.env` (or set Render environment variables):

```env
APP_ENV=production
DEMO_MODE=true
RAZORPAY_KEY_ID=rzp_test_your_key_id
RAZORPAY_KEY_SECRET=your_key_secret
RAZORPAY_WEBHOOK_SECRET=your_webhook_secret
```

---

## Attribution & License

Built on top of the deterministic payment recovery infrastructure created by **Ugo Chukwu / Etherlabs**.
Extended and transformed into the **AI Revenue Recovery Agent** platform for the **Razorpay Hackathon 2026**.

Licensed under the MIT License. See [`LICENSE`](./LICENSE).
