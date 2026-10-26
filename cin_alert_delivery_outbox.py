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
    status TEXT NOT NULL CHECK(status IN ('pending','sending','sent','failed')),
    attempts INTEGER NOT NULL DEFAULT 0,
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


def _connect(path: str | Path) -> sqlite3.Connection:
    target = str(path)
    if target != ":memory:":
        Path(target).parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(target, timeout=10, isolation_level=None)
    connection.execute("PRAGMA busy_timeout = 10000")
    connection.executescript(_SCHEMA)
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
) -> list[dict[str, Any]]:
    """Atomically claim due pending/failed items for a single worker invocation."""
    current = _timestamp(now, "now").isoformat()
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
        raise ValueError("limit must be an integer from 1 through 100")
    with _connect(database_path) as db:
        db.execute("BEGIN IMMEDIATE")
        try:
            rows = db.execute(
                """SELECT idempotency_key,rule_id,observation_id,payload_json,status,
                attempts,next_attempt_at,created_at,updated_at,last_error_code
                FROM alert_delivery_outbox
                WHERE status IN ('pending','failed') AND next_attempt_at <= ?
                ORDER BY created_at,idempotency_key LIMIT ?""",
                (current, limit),
            ).fetchall()
            claimed = []
            for row in rows:
                db.execute(
                    """UPDATE alert_delivery_outbox SET status='sending',updated_at=?
                    WHERE idempotency_key=? AND status IN ('pending','failed')""",
                    (current, row[0]),
                )
                claimed.append(_row((*row[:4], "sending", *row[5:])))
            db.execute("COMMIT")
            return claimed
        except Exception:
            if db.in_transaction:
                db.execute("ROLLBACK")
            raise


def mark_alert_sent(database_path: str | Path, idempotency_key: str, *, now: datetime | str) -> dict[str, Any]:
    current = _timestamp(now, "now").isoformat()
    with _connect(database_path) as db:
        db.execute("BEGIN IMMEDIATE")
        try:
            changed = db.execute(
                """UPDATE alert_delivery_outbox SET status='sent',attempts=attempts+1,
                updated_at=?,last_error_code=NULL WHERE idempotency_key=? AND status='sending'""",
                (current, idempotency_key),
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
) -> dict[str, Any]:
    """Record a bounded retry schedule; callers should pass sanitized error codes only."""
    current_dt = _timestamp(now, "now")
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
                "SELECT attempts,status FROM alert_delivery_outbox WHERE idempotency_key=?",
                (idempotency_key,),
            ).fetchone()
            if not row or row[1] != "sending":
                raise ValueError("outbox item must exist and be in sending state")
            attempts = row[0] + 1
            status = "failed" if attempts < max_attempts else "sent"
            # Exhausted items are terminal and never retried; status 'sent' is avoided
            # because it would falsely imply successful delivery.
            if attempts >= max_attempts:
                status = "failed"
            delay = min(retry_delay_seconds * (2 ** (attempts - 1)), 86400)
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
