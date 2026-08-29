-- Synthetic fixtures only. These rows demonstrate state handling and make no
-- claim about recovery rates, revenue, or production behavior.
INSERT INTO recovery_cases (
    provider_payment_intent_id,
    provider_customer_id,
    customer_email,
    amount_minor,
    currency,
    failure_category,
    provider_failure_code,
    status,
    attempts_completed,
    max_attempts,
    next_retry_at,
    policy_version
) VALUES
    (
        'pi_synthetic_insufficient_001',
        'cus_synthetic_001',
        'synthetic-funds@example.invalid',
        4900,
        'USD',
        'insufficient_funds',
        'insufficient_funds',
        'pending',
        0,
        3,
        now() - interval '1 minute',
        '2026-08-09'
    ),
    (
        'pi_synthetic_expired_001',
        'cus_synthetic_002',
        'synthetic-expired@example.invalid',
        9900,
        'USD',
        'invalid_payment_method',
        'expired_card',
        'action_required',
        0,
        0,
        NULL,
        '2026-08-09'
    ),
    (
        'pi_synthetic_security_001',
        'cus_synthetic_003',
        NULL,
        14900,
        'USD',
        'security_or_fraud',
        'fraudulent',
        'manual_review',
        0,
        0,
        NULL,
        '2026-08-09'
    )
ON CONFLICT (provider, provider_payment_intent_id) DO NOTHING;
