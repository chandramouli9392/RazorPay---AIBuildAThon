import os
import time
from pathlib import Path

import pytest

try:
    import psycopg
    from psycopg import errors
except ImportError:
    psycopg = None
    errors = None

ROOT = Path(__file__).parents[1]
DATABASE_URL = os.environ.get("DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL or psycopg is None,
    reason="DATABASE_URL is not configured or psycopg is not installed",
)


def connect():
    last_error = None
    for _ in range(30):
        try:
            return psycopg.connect(DATABASE_URL, autocommit=True)
        except psycopg.OperationalError as exc:
            last_error = exc
            time.sleep(0.2)
    raise last_error


def test_schema_retry_claim_idempotency_and_terminal_versioning():
    with connect() as connection:
        database_name = connection.execute("SELECT current_database()").fetchone()[0]
        assert database_name == "recovery_test" or database_name == "payment_recovery_test"
        connection.execute(
            "DROP TABLE IF EXISTS recovery_transitions, notification_deliveries, "
            "retry_attempts, recovery_cases, webhook_events CASCADE"
        )
        connection.execute((ROOT / "database/schema.sql").read_text())
        connection.execute((ROOT / "database/sample-data.sql").read_text())
        connection.execute((ROOT / "database/sample-data.sql").read_text())

        first = connection.execute(
            "SELECT id, version FROM claim_due_retries(%s, %s, %s)", ("worker-a", 10, 60)
        ).fetchall()
        second = connection.execute(
            "SELECT id FROM claim_due_retries(%s, %s, %s)", ("worker-b", 10, 60)
        ).fetchall()
        assert len(first) == 1
        assert second == []
        case_id, _ = first[0]

        connection.execute(
            "UPDATE recovery_cases SET lease_expires_at = now() - interval '1 second' "
            "WHERE id = %s",
            (case_id,),
        )
        reclaimed = connection.execute(
            "SELECT id, version FROM claim_due_retries(%s, %s, %s)", ("worker-b", 10, 60)
        ).fetchall()
        assert len(reclaimed) == 1
        assert reclaimed[0][0] == case_id
        version = reclaimed[0][1]

        connection.execute(
            """INSERT INTO retry_attempts
            (recovery_case_id, attempt_number, provider_idempotency_key, status)
            VALUES (%s, 1, %s, 'claimed')""",
            (case_id, f"retry:{case_id}:1"),
        )
        with pytest.raises(errors.UniqueViolation):
            connection.execute(
                """INSERT INTO retry_attempts
                (recovery_case_id, attempt_number, provider_idempotency_key, status)
                VALUES (%s, 1, 'duplicate-key', 'claimed')""",
                (case_id,),
            )

        connection.execute(
            "INSERT INTO notification_deliveries "
            "(recovery_case_id, notification_kind) VALUES (%s, %s)",
            (case_id, "insufficient_funds"),
        )
        with pytest.raises(errors.UniqueViolation):
            connection.execute(
                "INSERT INTO notification_deliveries "
                "(recovery_case_id, notification_kind) VALUES (%s, %s)",
                (case_id, "insufficient_funds"),
            )

        assert connection.execute(
            "SELECT mark_recovery_terminal(%s, %s, 'recovered')", (case_id, version)
        ).fetchone() == (True,)
        assert connection.execute(
            "SELECT mark_recovery_terminal(%s, %s, 'cancelled')", (case_id, version)
        ).fetchone() == (False,)
        assert connection.execute(
            "SELECT status, next_retry_at FROM recovery_cases WHERE id = %s", (case_id,)
        ).fetchone() == ("recovered", None)
