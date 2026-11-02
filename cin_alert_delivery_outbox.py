"""Durable, transport-neutral outbox for CIN alert notifications.

This module records delivery intent and retry state only. It never contacts a
notification provider. A separate authorized adapter must deliver claimed
payloads and call mark_sent/mark_failed.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping


_SCHEMA = """
CREATE TABLE IF NOT EXISTS alert_delivery_outbox (
    idempotency_key TEXT PRIMARY KEY,
    rule_id TEXT NOT NULL,
    observation_id TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('pending','sending','sent','failed','dead','uncertain')),
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    next_attempt_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_error_code TEXT
);
CREATE INDEX IF NOT EXISTS idx_alert_outbox_due
ON alert_delivery_outbox(status, next_attempt_at);
"""


def _timestamp(value: datetime | str, field: str) -> datetime:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"{field} must be an ISO-8601 timestamp") from exc
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must include an explicit timezone")
    return value.astimezone(timezone.utc)


def _migrate_outbox_schema(connection: sqlite3.Connection) -> None:
    """Rebuild legacy outbox tables whose status CHECK excludes 'uncertain'."""
    row = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='alert_delivery_outbox'"
    ).fetchone()
    if not row:
        return
    schema_sql = (row[0] or "").lower()
    # Upgrade either legacy constraint independently: an intermediate schema
    # may already allow 'uncertain' but still permit negative attempt counts.
    if "uncertain" in schema_sql and "check (attempts >= 0)" in schema_sql:
        return

    # SQLite cannot alter a CHECK constraint in place. Rebuild transactionally,
    # preserving every existing outbox row and recreating its index.
    connection.execute("BEGIN IMMEDIATE")
    try:
        connection.execute("DROP INDEX IF EXISTS idx_alert_outbox_due")
        connection.execute("DROP INDEX IF EXISTS idx_alert_delivery_outbox_due")
        connection.execute(
            """CREATE TABLE alert_delivery_outbox_new (
                idempotency_key TEXT PRIMARY KEY,
                rule_id TEXT NOT NULL,
                observation_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('pending','sending','sent','failed','dead','uncertain')),
                attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
                next_attempt_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_error_code TEXT
            )"""
        )
        connection.execute(
            """INSERT INTO alert_delivery_outbox_new
            (idempotency_key,rule_id,observation_id,payload_json,status,attempts,
             next_attempt_at,created_at,updated_at,last_error_code)
            SELECT idempotency_key,rule_id,observation_id,payload_json,status,attempts,
                   next_attempt_at,created_at,updated_at,last_error_code
            FROM alert_delivery_outbox"""
        )
        connection.execute("DROP TABLE alert_delivery_outbox")
        connection.execute("ALTER TABLE alert_delivery_outbox_new RENAME TO alert_delivery_outbox")
        connection.execute(
            "CREATE INDEX idx_alert_outbox_due ON alert_delivery_outbox(status, next_attempt_at)"
        )
        # Preserve the index created by the state-store schema as well.
        connection.execute(
            "CREATE INDEX idx_alert_delivery_outbox_due ON alert_delivery_outbox(status, next_attempt_at)"
        )
        connection.execute("COMMIT")
    except Exception:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise


def _connect(path: str | Path) -> sqlite3.Connection:
    target = str(path)
    if target == ":memory:":
        raise ValueError("a persistent SQLite file path is required; separate outbox calls open separate connections")
    Path(target).parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(target, timeout=10, isolation_level=None)
    connection.execute("PRAGMA busy_timeout = 10000")
    connection.executescript(_SCHEMA)
    _migrate_outbox_schema(connection)
    return connection


def enqueue_alert_delivery(
    database_path: str | Path,
    *,
    rule_id: str,
    observation_id: str,
    payload: Mapping[str, Any],
    now: datetime | str,
) -> dict[str, Any]:
    """Insert delivery intent idempotently; repeated key returns existing state."""
    if not isinstance(rule_id, str) or not rule_id.strip():
        raise ValueError("rule_id must be a non-empty string")
    if not isinstance(observation_id, str) or not observation_id.strip():
        raise ValueError("observation_id must be a non-empty string")
    if not isinstance(payload, Mapping):
        raise ValueError("payload must be a mapping")
    current = _timestamp(now, "now").isoformat()
    key = f"{rule_id}:{observation_id}"
    encoded = json.dumps(dict(payload), sort_keys=True, separators=(",", ":"), allow_nan=False)
    with _connect(database_path) as db:
        db.execute("BEGIN IMMEDIATE")
        try:
            db.execute(
                """INSERT OR IGNORE INTO alert_delivery_outbox
                (idempotency_key,rule_id,observation_id,payload_json,status,attempts,
                 next_attempt_at,created_at,updated_at,last_error_code)
                VALUES (?,?,?,?,'pending',0,?,?,?,NULL)""",
                (key, rule_id, observation_id, encoded, current, current, current),
            )
            row = db.execute(
                """SELECT idempotency_key,rule_id,observation_id,payload_json,status,
                attempts,next_attempt_at,created_at,updated_at,last_error_code
                FROM alert_delivery_outbox WHERE idempotency_key=?""",
                (key,),
            ).fetchone()
            db.execute("COMMIT")
        except Exception:
            if db.in_transaction:
                db.execute("ROLLBACK")
            raise
    return _row(row)


def _row(row: tuple[Any, ...]) -> dict[str, Any]:
    names = ("idempotency_key","rule_id","observation_id","payload","status",
             "attempts","next_attempt_at","created_at","updated_at","last_error_code")
    values = list(row)
    values[3] = json.loads(values[3])
    return dict(zip(names, values))


def claim_due_alerts(
    database_path: str | Path,
    *,
    now: datetime | str,
    limit: int = 10,
    lease_seconds: int = 300,
    max_attempts: int = 5,
) -> list[dict[str, Any]]:
    """Claim due work and recover abandoned sending leases after worker crashes."""
    current_dt = _timestamp(now, "now")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
        raise ValueError("limit must be an integer from 1 through 100")
    if isinstance(lease_seconds, bool) or not isinstance(lease_seconds, int) or not 30 <= lease_seconds <= 3600:
        raise ValueError("lease_seconds must be an integer from 30 through 3600")
    if isinstance(max_attempts, bool) or not isinstance(max_attempts, int) or not 1 <= max_attempts <= 20:
        raise ValueError("max_attempts must be an integer from 1 through 20")
    current = current_dt.isoformat()
    stale_before = (current_dt - timedelta(seconds=lease_seconds)).isoformat()
    with _connect(database_path) as db:
        db.execute("BEGIN IMMEDIATE")
        try:
            db.execute(
                """UPDATE alert_delivery_outbox
                SET status='dead',updated_at=?,last_error_code='worker_lease_expired_max_attempts'
                WHERE status='sending' AND updated_at <= ? AND attempts >= ?""",
                (current, stale_before, max_attempts),
            )
            # An expired lease has an unknown provider outcome. Never blindly resend it:
            # the provider may have accepted the message before the worker crashed.
            db.execute(
                """UPDATE alert_delivery_outbox
                SET status='uncertain',updated_at=?,
                    last_error_code='delivery_outcome_unknown'
                WHERE status='sending' AND updated_at <= ? AND attempts < ?""",
                (current, stale_before, max_attempts),
            )
            # A runtime reduction of max_attempts must not allow an already
            # exhausted failed item to be sent again. Explicit operator-authorized
            # retries from an uncertain outcome remain claimable, even at the cap.
            db.execute(
                """UPDATE alert_delivery_outbox
                SET status='dead',updated_at=?,last_error_code='max_attempts_reached'
                WHERE status='failed' AND attempts >= ?""",
                (current, max_attempts),
            )
            rows = db.execute(
                """SELECT idempotency_key,rule_id,observation_id,payload_json,status,
                attempts,next_attempt_at,created_at,updated_at,last_error_code
                FROM alert_delivery_outbox
                WHERE status IN ('pending','failed') AND next_attempt_at <= ?
                  AND (attempts < ? OR
                       (status='pending' AND last_error_code='operator_authorized_retry_duplicate_risk'))
                ORDER BY created_at,idempotency_key LIMIT ?""",
                (current, max_attempts, limit),
            ).fetchall()
            claimed = []
            for row in rows:
                db.execute(
                    """UPDATE alert_delivery_outbox SET status='sending',attempts=attempts+1,updated_at=?
                    WHERE idempotency_key=? AND status IN ('pending','failed')
                      AND next_attempt_at <= ?""",
                    (current, row[0], current),
                )
                updated = db.execute(
                    """SELECT idempotency_key,rule_id,observation_id,payload_json,status,
                    attempts,next_attempt_at,created_at,updated_at,last_error_code
                    FROM alert_delivery_outbox WHERE idempotency_key=?""",
                    (row[0],),
                ).fetchone()
                claimed.append(_row(updated))
            db.execute("COMMIT")
            return claimed
        except Exception:
            if db.in_transaction:
                db.execute("ROLLBACK")
            raise


def _validate_claim_lease(
    claim_updated_at: str, current_dt: datetime, lease_seconds: int
) -> None:
    if (
        isinstance(lease_seconds, bool)
        or not isinstance(lease_seconds, int)
        or not 30 <= lease_seconds <= 3600
    ):
        raise ValueError("lease_seconds must be an integer from 30 through 3600")
    claim_time = _timestamp(claim_updated_at, "claim_updated_at")
    if current_dt >= claim_time + timedelta(seconds=lease_seconds):
        raise ValueError("worker claim lease has expired")


def mark_alert_sent(
    database_path: str | Path, idempotency_key: str, *,
    now: datetime | str, claim_attempt: int, lease_seconds: int = 300
) -> dict[str, Any]:
    if isinstance(claim_attempt, bool) or not isinstance(claim_attempt, int) or claim_attempt < 1:
        raise ValueError("claim_attempt must be a positive integer")
    current_dt = _timestamp(now, "now")
    current = current_dt.isoformat()
    with _connect(database_path) as db:
        db.execute("BEGIN IMMEDIATE")
        try:
            claim = db.execute(
                "SELECT status,attempts,updated_at FROM alert_delivery_outbox WHERE idempotency_key=?",
                (idempotency_key,),
            ).fetchone()
            if not claim or claim[0] != "sending" or claim[1] != claim_attempt:
                raise ValueError("outbox item must exist and be in sending state")
            _validate_claim_lease(claim[2], current_dt, lease_seconds)
            changed = db.execute(
                """UPDATE alert_delivery_outbox SET status='sent',
                updated_at=?,last_error_code=NULL
                WHERE idempotency_key=? AND status='sending' AND attempts=? AND updated_at=?""",
                (current, idempotency_key, claim_attempt, claim[2]),
            ).rowcount
            if not changed:
                raise ValueError("outbox item must exist and be in sending state")
            row = db.execute(
                """SELECT idempotency_key,rule_id,observation_id,payload_json,status,
                attempts,next_attempt_at,created_at,updated_at,last_error_code
                FROM alert_delivery_outbox WHERE idempotency_key=?""",
                (idempotency_key,),
            ).fetchone()
            db.execute("COMMIT")
            return _row(row)
        except Exception:
            if db.in_transaction:
                db.execute("ROLLBACK")
            raise


def mark_alert_failed(
    database_path: str | Path,
    idempotency_key: str,
    *,
    now: datetime | str,
    error_code: str,
    retry_delay_seconds: int = 60,
    max_attempts: int = 5,
    claim_attempt: int,
    lease_seconds: int = 300,
) -> dict[str, Any]:
    """Record a bounded retry schedule for the current, unexpired claim only."""
    current_dt = _timestamp(now, "now")
    if isinstance(claim_attempt, bool) or not isinstance(claim_attempt, int) or claim_attempt < 1:
        raise ValueError("claim_attempt must be a positive integer")
    if not isinstance(error_code, str) or not error_code or len(error_code) > 80:
        raise ValueError("error_code must be a non-empty sanitized code of at most 80 characters")
    if isinstance(retry_delay_seconds, bool) or not isinstance(retry_delay_seconds, int) or not 1 <= retry_delay_seconds <= 86400:
        raise ValueError("retry_delay_seconds must be an integer from 1 through 86400")
    if isinstance(max_attempts, bool) or not isinstance(max_attempts, int) or not 1 <= max_attempts <= 20:
        raise ValueError("max_attempts must be an integer from 1 through 20")
    current = current_dt.isoformat()
    with _connect(database_path) as db:
        db.execute("BEGIN IMMEDIATE")
        try:
            row = db.execute(
                "SELECT attempts,status,updated_at FROM alert_delivery_outbox WHERE idempotency_key=?",
                (idempotency_key,),
            ).fetchone()
            if not row or row[1] != "sending" or row[0] != claim_attempt:
                raise ValueError("outbox item must exist and be in sending state")
            _validate_claim_lease(row[2], current_dt, lease_seconds)
            attempts = row[0]
            # Attempts are counted when work is claimed, including recovered leases.
            status = "failed" if attempts < max_attempts else "dead"
            delay = min(retry_delay_seconds * (2 ** max(0, attempts - 1)), 86400)
            next_attempt = (current_dt + timedelta(seconds=delay)).isoformat()
            db.execute(
                """UPDATE alert_delivery_outbox SET status=?,attempts=?,next_attempt_at=?,
                updated_at=?,last_error_code=? WHERE idempotency_key=?""",
                (status, attempts, next_attempt, current, error_code, idempotency_key),
            )
            updated = db.execute(
                """SELECT idempotency_key,rule_id,observation_id,payload_json,status,
                attempts,next_attempt_at,created_at,updated_at,last_error_code
                FROM alert_delivery_outbox WHERE idempotency_key=?""",
                (idempotency_key,),
            ).fetchone()
            db.execute("COMMIT")
            return _row(updated)
        except Exception:
            if db.in_transaction:
                db.execute("ROLLBACK")
            raise



def list_uncertain_alert_deliveries(database_path: str | Path, *, limit: int = 100) -> list[dict[str, Any]]:
    """Return uncertain outcomes for operator reconciliation; never sends messages."""
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 500:
        raise ValueError("limit must be an integer from 1 through 500")
    with _connect(database_path) as db:
        rows = db.execute(
            """SELECT idempotency_key,rule_id,observation_id,payload_json,status,
            attempts,next_attempt_at,created_at,updated_at,last_error_code
            FROM alert_delivery_outbox WHERE status='uncertain'
            ORDER BY updated_at,idempotency_key LIMIT ?""",
            (limit,),
        ).fetchall()
    return [_row(row) for row in rows]


def resolve_uncertain_alert_delivery(
    database_path: str | Path,
    idempotency_key: str,
    *,
    resolution: str,
    now: datetime | str,
) -> dict[str, Any]:
    """Resolve an uncertain outcome as sent, or explicitly authorize a retry.

    'retry_authorized' changes the item back to pending. This is an operator
    decision and can produce a duplicate if the provider accepted the original.
    """
    if resolution not in {"sent", "retry_authorized"}:
        raise ValueError("resolution must be 'sent' or 'retry_authorized'")
    current = _timestamp(now, "now").isoformat()
    if resolution == "retry_authorized":
        status = "pending"
        error_code = "operator_authorized_retry_duplicate_risk"
    else:
        status = "sent"
        error_code = None
    with _connect(database_path) as db:
        db.execute("BEGIN IMMEDIATE")
        try:
            changed = db.execute(
                """UPDATE alert_delivery_outbox SET status=?,updated_at=?,last_error_code=?
                WHERE idempotency_key=? AND status='uncertain'""",
                (status, current, error_code, idempotency_key),
            ).rowcount
            if not changed:
                raise ValueError("outbox item must exist and be in uncertain state")
            row = db.execute(
                """SELECT idempotency_key,rule_id,observation_id,payload_json,status,
                attempts,next_attempt_at,created_at,updated_at,last_error_code
                FROM alert_delivery_outbox WHERE idempotency_key=?""",
                (idempotency_key,),
            ).fetchone()
            db.execute("COMMIT")
            return _row(row)
        except Exception:
            if db.in_transaction:
                db.execute("ROLLBACK")
            raise
