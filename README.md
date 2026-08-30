<div align="center">

<img src="https://readme-typing-svg.demolab.com?font=Fira+Code&weight=700&size=30&duration=3500&pause=1000&color=3395FF&center=true&vCenter=true&width=850&lines=⚡+Razorpay+AI+Revenue+Recovery+Agent;🤖+AI-Powered+Revenue+Intelligence;💰+Detect.+Predict.+Recover." alt="Typing SVG" />

<br/>

<img src="https://img.shields.io/badge/Razorpay-AI%20Build%20A%20Thon-3395FF?style=for-the-badge&logo=razorpay&logoColor=white" />

<img src="https://img.shields.io/badge/Track-03%20AI%20Revenue%20Recovery-7B61FF?style=for-the-badge" />

<img src="https://img.shields.io/badge/Status-Hackathon%20Ready-00C853?style=for-the-badge" />

</div>

# Razorpay AI Revenue Recovery Agent

### An explainable AI-powered system for detecting revenue leakage and intelligently recovering lost payment revenue.

> **Razorpay AI Build A Thon · Track 03**

---

## Overview

Payment failures, abandoned checkouts, failed subscriptions, and overdue receivables can lead to significant revenue leakage.

Traditional recovery systems usually rely on fixed rules such as retrying a payment after a predefined interval. This project takes a more intelligent approach.

The **Razorpay AI Revenue Recovery Agent** analyzes revenue leakage events, identifies possible root causes, predicts recovery probability, evaluates multiple interventions, and selects an optimal recovery strategy while applying deterministic safety guardrails.

### Recovery Flow

**Detect → Analyze → Predict → Decide → Protect → Recover**

---

## Key Features

### AI-Powered Recovery Decisions

- Detects revenue leakage events
- Performs root cause analysis
- Predicts recovery probability using ML
- Calculates expected recovery value
- Evaluates multiple candidate interventions
- Selects the optimal intervention

### Explainable AI

Every recovery decision can be inspected through an AI decision matrix containing:

- Customer context
- Revenue event details
- Root cause analysis
- Recovery probability
- Candidate interventions
- Cost and friction scores
- Expected recovery value
- Selected intervention
- Guardrail evaluation

### Safety Guardrails

The system includes deterministic controls such as:

- Retry limits
- Contact frequency protection
- Duplicate action prevention
- High-value transaction escalation
- Risk and fraud checks
- Human approval workflows

### Human Review Queue

High-risk or sensitive cases can be routed to a human reviewer.

Reviewers can:

- Approve an intervention
- Reject an intervention
- Modify the selected action
- Execute approved recovery actions
- Review the complete AI decision matrix

---

## Dashboard

The application includes a real-time dashboard showing:

- **Revenue At Risk**
- **Expected Recoverable Revenue**
- **Actual Revenue Recovered**
- **Incremental Revenue vs Rule-Based Policy**
- **Recovery Rate**
- **Human Review Queue**
- **AI vs Baseline Benchmark**
- **Revenue Leakage Category Breakdown**
- **Active Recovery Cases**

---

## Technology Stack

### Backend

- Python
- FastAPI
- PostgreSQL

### AI and Decision Engine

- Machine Learning
- Recovery Probability Prediction
- Intervention Optimization
- Explainable Decision Scoring

### Infrastructure

- Docker
- Docker Compose
- GitHub Actions
- Render

### Testing and Code Quality

- Pytest
- Ruff

---

## Project Structure

```text
RazorPay---AIBuildAThon/
│
├── .github/                 # GitHub Actions workflows
├── database/                # Database configuration
├── docs/                    # Documentation
├── email-templates/         # Recovery communication templates
├── n8n-workflows/           # Automation workflows
├── src/                     # Application source code
├── tests/                   # Automated tests
│
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── evaluate_recovery.py     # Benchmark evaluation
├── verify_endpoints.py      # API verification
├── render.yaml              # Render deployment configuration
├── start.sh                 # Production startup script
│
└── README.md
How It Works
Payment / Revenue Event
          ↓
Revenue Leakage Detection
          ↓
Root Cause Analysis
          ↓
ML Recovery Probability Prediction
          ↓
Evaluate Candidate Interventions
          ↓
Safety Guardrail Evaluation
          ↓
   ┌───────────────┐
   │               │
Auto Approval   Human Review
   │               │
   └───────┬───────┘
           ↓
Controlled Recovery Action
           ↓
Revenue Outcome + Audit Trail
Candidate Interventions

The AI Agent evaluates multiple recovery strategies depending on the type and context of the event.

Examples include:

Update payment method
Smart payment retry
Payment reminder
Invoice reminder
Checkout recovery
Delayed retry
Alternative recovery strategy
Human escalation
No action

The final decision considers recovery probability, expected revenue, intervention cost, customer friction, risk, and safety constraints.

Running Locally
Clone the repository
git clone https://github.com/chandramouli9392/RazorPay---AIBuildAThon.git
cd RazorPay---AIBuildAThon
Create a virtual environment

Windows

python -m venv .venv
.venv\Scripts\activate

Linux/macOS

python -m venv .venv
source .venv/bin/activate
Install dependencies
python -m pip install --upgrade pip
pip install -e ".[dev]"
Running Tests
python -m pytest

Run code quality checks:

ruff check .
Running with Docker
docker compose up --build

This starts the application and PostgreSQL services.

Benchmark Evaluation

Run the recovery benchmark:

python evaluate_recovery.py

The benchmark evaluates AI-driven recovery strategies against baseline policies.

Key metrics include:

Revenue at Risk
Expected Recoverable Revenue
Actual Revenue Recovered
Recovery Rate
Incremental Revenue
AI vs Rule-Based Performance
Responsible AI

The project is designed to keep recovery decisions explainable and controlled.

The evaluation and decision pipeline is designed to avoid:

Target leakage
Oracle action selection
Circular ground truth
Fake recovery outcomes

High-risk actions can be routed through human review and deterministic safety guardrails.

Built For

Razorpay AI Build A Thon

Razorpay AI Revenue Recovery Agent

Detect revenue leakage. Understand the cause. Predict recovery. Take the right action.| **F1-Score / ROC-AUC** | N/A | N/A | **70.1% F1 / 0.912 ROC-AUC** | High Calibrated Discrimination |
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
