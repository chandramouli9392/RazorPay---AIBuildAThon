\set ON_ERROR_STOP on

BEGIN;

-- Seed data is explicitly synthetic and safe to rerun.
\ir ../../database/sample-data.sql
\ir ../../database/sample-data.sql

DO $$
DECLARE
    case_id uuid;
    first_claim_count integer;
    second_claim_count integer;
    current_version integer;
BEGIN
    SELECT id INTO case_id
      FROM recovery_cases
     WHERE provider_payment_intent_id = 'pi_synthetic_insufficient_001';

    SELECT count(*) INTO first_claim_count FROM claim_due_retries('worker-a', 10, 60);
    SELECT count(*) INTO second_claim_count FROM claim_due_retries('worker-b', 10, 60);
    IF first_claim_count <> 1 OR second_claim_count <> 0 THEN
        RAISE EXCEPTION 'atomic claim failed: first %, second %', first_claim_count, second_claim_count;
    END IF;

    UPDATE recovery_cases
       SET lease_expires_at = now() - interval '1 second'
     WHERE id = case_id;
    SELECT count(*) INTO second_claim_count FROM claim_due_retries('worker-b', 10, 60);
    IF second_claim_count <> 1 THEN
        RAISE EXCEPTION 'expired lease was not reclaimed';
    END IF;

    INSERT INTO retry_attempts (
        recovery_case_id, attempt_number, provider_idempotency_key, status
    ) VALUES (case_id, 1, 'retry:' || case_id || ':1', 'claimed');

    BEGIN
        INSERT INTO retry_attempts (
            recovery_case_id, attempt_number, provider_idempotency_key, status
        ) VALUES (case_id, 1, 'different-key', 'claimed');
        RAISE EXCEPTION 'duplicate retry attempt was accepted';
    EXCEPTION WHEN unique_violation THEN
        NULL;
    END;

    INSERT INTO notification_deliveries (recovery_case_id, notification_kind)
    VALUES (case_id, 'insufficient_funds');
    BEGIN
        INSERT INTO notification_deliveries (recovery_case_id, notification_kind)
        VALUES (case_id, 'insufficient_funds');
        RAISE EXCEPTION 'duplicate notification was accepted';
    EXCEPTION WHEN unique_violation THEN
        NULL;
    END;

    SELECT version INTO current_version FROM recovery_cases WHERE id = case_id;
    IF NOT mark_recovery_terminal(case_id, current_version, 'recovered') THEN
        RAISE EXCEPTION 'expected terminal transition to apply';
    END IF;
    IF mark_recovery_terminal(case_id, current_version, 'cancelled') THEN
        RAISE EXCEPTION 'stale version overwrote terminal transition';
    END IF;
    IF EXISTS (
        SELECT 1 FROM recovery_cases
        WHERE id = case_id AND (status <> 'recovered' OR next_retry_at IS NOT NULL)
    ) THEN
        RAISE EXCEPTION 'recovery did not cancel future retry';
    END IF;
END;
$$;

ROLLBACK;
