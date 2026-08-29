BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS webhook_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    provider text NOT NULL CHECK (provider <> ''),
    provider_event_id text NOT NULL CHECK (provider_event_id <> ''),
    event_type text NOT NULL CHECK (event_type <> ''),
    payload_sha256 text NOT NULL CHECK (payload_sha256 ~ '^[0-9a-f]{64}$'),
    received_at timestamptz NOT NULL DEFAULT now(),
    processed_at timestamptz,
    processing_status text NOT NULL DEFAULT 'received'
        CHECK (processing_status IN ('received', 'processed', 'rejected', 'failed')),
    error_message text,
    UNIQUE (provider, provider_event_id)
);

CREATE TABLE IF NOT EXISTS customers (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    provider text NOT NULL DEFAULT 'razorpay',
    provider_customer_id text NOT NULL UNIQUE,
    name text NOT NULL,
    email text NOT NULL,
    ltv_minor bigint NOT NULL DEFAULT 0,
    historical_success_rate numeric(5, 4) NOT NULL DEFAULT 1.0,
    segment text NOT NULL DEFAULT 'Standard',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS revenue_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id text NOT NULL UNIQUE,
    provider text NOT NULL DEFAULT 'razorpay',
    event_type text NOT NULL,
    leakage_type text NOT NULL CHECK (leakage_type IN (
        'failed_payment', 'failed_subscription', 'checkout_abandonment', 'overdue_receivable'
    )),
    occurred_at timestamptz NOT NULL,
    customer_id text NOT NULL,
    payment_id text,
    order_id text,
    subscription_id text,
    invoice_id text,
    amount_inr numeric(12, 2) NOT NULL DEFAULT 0.0,
    currency text NOT NULL DEFAULT 'INR',
    status text NOT NULL,
    failure_code text,
    failure_reason text,
    raw_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS revenue_events_customer_idx ON revenue_events(customer_id);
CREATE INDEX IF NOT EXISTS revenue_events_leakage_idx ON revenue_events(leakage_type);
CREATE INDEX IF NOT EXISTS revenue_events_occurred_idx ON revenue_events(occurred_at);

CREATE TABLE IF NOT EXISTS recovery_cases (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    provider text NOT NULL DEFAULT 'razorpay',
    provider_payment_intent_id text NOT NULL CHECK (provider_payment_intent_id <> ''),
    provider_customer_id text,
    customer_email text,
    amount_minor bigint NOT NULL CHECK (amount_minor >= 0),
    currency text NOT NULL CHECK (currency ~ '^[A-Z]{3}$'),
    failure_category text NOT NULL CHECK (failure_category IN (
        'insufficient_funds', 'invalid_payment_method', 'authentication_required',
        'security_or_fraud', 'temporary_processing', 'subscription_halted',
        'checkout_abandoned', 'invoice_overdue', 'hard_decline', 'unknown'
    )),
    provider_failure_code text NOT NULL,
    status text NOT NULL CHECK (status IN (
        'pending', 'attempting', 'action_required', 'manual_review', 'recovered', 'exhausted', 'cancelled', 'executing', 'intervention_sent'
    )),
    attempts_completed integer NOT NULL DEFAULT 0 CHECK (attempts_completed >= 0),
    max_attempts integer NOT NULL CHECK (max_attempts >= 0),
    next_retry_at timestamptz,
    policy_version text NOT NULL,
    version integer NOT NULL DEFAULT 1 CHECK (version > 0),
    lease_owner text,
    lease_expires_at timestamptz,
    recovered_at timestamptz,
    cancelled_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (provider, provider_payment_intent_id)
);

CREATE INDEX IF NOT EXISTS recovery_cases_due_idx
    ON recovery_cases (next_retry_at)
    WHERE status = 'pending';

CREATE TABLE IF NOT EXISTS recovery_predictions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id text NOT NULL REFERENCES revenue_events(event_id) ON DELETE CASCADE,
    recovery_probability numeric(5, 4) NOT NULL,
    confidence numeric(5, 4) NOT NULL,
    expected_recovery_value numeric(12, 2) NOT NULL,
    model_version text NOT NULL,
    top_features jsonb NOT NULL DEFAULT '[]'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS recovery_decisions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    decision_id text NOT NULL UNIQUE,
    event_id text NOT NULL REFERENCES revenue_events(event_id) ON DELETE CASCADE,
    recommended_action text NOT NULL,
    reasoning text NOT NULL,
    expected_net_recovery numeric(12, 2) NOT NULL,
    estimated_cost numeric(12, 2) NOT NULL,
    timing_delay_hours integer NOT NULL DEFAULT 0,
    requires_human boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS recovery_actions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    action_id text NOT NULL UNIQUE,
    event_id text NOT NULL REFERENCES revenue_events(event_id) ON DELETE CASCADE,
    customer_id text NOT NULL,
    action_type text NOT NULL,
    status text NOT NULL,
    amount_at_risk numeric(12, 2) NOT NULL,
    expected_recovery numeric(12, 2) NOT NULL,
    actual_recovery numeric(12, 2) NOT NULL DEFAULT 0.0,
    provider_response_id text,
    is_simulation boolean NOT NULL DEFAULT true,
    executed_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    audit_id text NOT NULL UNIQUE,
    event_id text NOT NULL REFERENCES revenue_events(event_id) ON DELETE CASCADE,
    customer_id text NOT NULL,
    leakage_type text NOT NULL,
    amount_at_risk numeric(12, 2) NOT NULL,
    root_cause jsonb NOT NULL,
    prediction jsonb NOT NULL,
    decision jsonb NOT NULL,
    guardrail jsonb NOT NULL,
    action jsonb,
    baseline_expected numeric(12, 2) NOT NULL DEFAULT 0.0,
    incremental_value numeric(12, 2) NOT NULL DEFAULT 0.0,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS audit_logs_event_idx ON audit_logs(event_id);
CREATE INDEX IF NOT EXISTS audit_logs_customer_idx ON audit_logs(customer_id);

COMMIT;
