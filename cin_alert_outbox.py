"""SQLite notification outbox primitives for CIN alert delivery adapters.

This module queues notification intent but never sends network requests. A caller
must provide an idempotency key and explicitly invoke a delivery adapter.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping


_SCHEMA = """
CREATE TABLE IF NOT EXISTS alert_notification_outbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    idempotency_key TEXT NOT NULL UNIQUE,
    payload_json TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'sending', 'sent', 'failed')),
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    next_attempt_at TEXT NOT NULL,
    sent_at TEXT,
    last_error TEXT
);
CREATE INDEX IF NOT EXISTS idx_alert_outbox_due
ON alert_notification_outbox(status, next_attempt_at, id);
"""


def _utc(value: datetime | str, field: str = "now") -> datetime:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"{field} must be an ISO-8601 timestamp") from exc
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must include an explicit timezone")
    return value.astimezone(timezone.utc)


def _connect(path: str | Path) -> sqlite3.Connection:
    value = str(path)
    if value == ":memory:":
        raise ValueError("a persistent SQLite file path is required; separate outbox calls open separate connections")
    Path(value).parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(value, timeout=10, isolation_level=None)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 10000")
    connection.executescript(_SCHEMA)
    return connection


def enqueue_notification(
    database_path: str | Path,
    *,
    idempotency_key: str,
    payload: Mapping[str, Any],
    now: datetime | str,
) -> dict[str, Any]:
    """Insert one pending delivery intent; repeated keys are idempotent."""
    if not isinstance(idempotency_key, str) or not idempotency_key.strip() or len(idempotency_key) > 200:
        raise ValueError("idempotency_key must be a non-empty string of at most 200 characters")
    if not isinstance(payload, Mapping):
        raise ValueError("payload must be a mapping")
    try:
        encoded = json.dumps(dict(payload), sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("payload must be JSON-serializable and contain no non-finite numbers") from exc
    timestamp = _utc(now).isoformat()
    connection = _connect(database_path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            """INSERT INTO alert_notification_outbox
               (idempotency_key, payload_json, status, attempts, created_at, updated_at, next_attempt_at)
               VALUES (?, ?, 'pending', 0, ?, ?, ?)
               ON CONFLICT(idempotency_key) DO NOTHING""",
            (idempotency_key, encoded, timestamp, timestamp, timestamp),
        )
        row = connection.execute(
            "SELECT * FROM alert_notification_outbox WHERE idempotency_key = ?",
            (idempotency_key,),
        ).fetchone()
        connection.execute("COMMIT")
        return dict(row)
    except Exception:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise
    finally:
        connection.close()


def claim_due_notifications(
    database_path: str | Path,
    *,
    now: datetime | str,
    limit: int = 10,
    lease_seconds: int = 300,
) -> list[dict[str, Any]]:
    """Claim due rows and reclaim stale worker leases after a crash."""
    current = _utc(now)
    timestamp = current.isoformat()
    stale_before = (current - timedelta(seconds=lease_seconds)).isoformat()
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
        raise ValueError("limit must be an integer from 1 through 100")
    if isinstance(lease_seconds, bool) or not isinstance(lease_seconds, int) or not 30 <= lease_seconds <= 3600:
        raise ValueError("lease_seconds must be an integer from 30 through 3600")
    connection = _connect(database_path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        rows = connection.execute(
            """SELECT id FROM alert_notification_outbox
               WHERE (status = 'pending' AND next_attempt_at <= ?)
                  OR (status = 'sending' AND updated_at <= ?)
               ORDER BY next_attempt_at, id LIMIT ?""",
            (timestamp, stale_before, limit),
        ).fetchall()
        ids = [row["id"] for row in rows]
        if ids:
            placeholders = ",".join("?" for _ in ids)
            connection.execute(
                f"""UPDATE alert_notification_outbox
                    SET status = 'sending', attempts = attempts + 1, updated_at = ?
                    WHERE id IN ({placeholders}) AND
                      (status = 'pending' OR (status = 'sending' AND updated_at <= ?))""",
                (timestamp, *ids, stale_before),
            )
        claimed = []
        for row_id in ids:
            row = connection.execute(
                "SELECT * FROM alert_notification_outbox WHERE id = ?", (row_id,)
            ).fetchone()
            if row and row["status"] == "sending":
                item = dict(row)
                item["payload"] = json.loads(item.pop("payload_json"))
                claimed.append(item)
        connection.execute("COMMIT")
        return claimed
    except Exception:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise
    finally:
        connection.close()


def mark_notification_sent(
    database_path: str | Path,
    *,
    notification_id: int,
    now: datetime | str,
) -> bool:
    """Mark a claimed notification sent. Returns False if it was not sending."""
    timestamp = _utc(now).isoformat()
    connection = _connect(database_path)
    try:
        cursor = connection.execute(
            """UPDATE alert_notification_outbox
               SET status = 'sent', sent_at = ?, updated_at = ?, last_error = NULL
               WHERE id = ? AND status = 'sending'""",
            (timestamp, timestamp, notification_id),
        )
        return cursor.rowcount == 1
    finally:
        connection.close()


def mark_notification_failed(
    database_path: str | Path,
    *,
    notification_id: int,
    error: str,
    now: datetime | str,
    max_attempts: int = 5,
    base_delay_seconds: int = 30,
) -> dict[str, Any] | None:
    """Record failure and schedule bounded exponential retry, or terminally fail."""
    current = _utc(now)
    if not isinstance(error, str) or not error.strip():
        raise ValueError("error must be a non-empty string")
    if isinstance(max_attempts, bool) or not isinstance(max_attempts, int) or not 1 <= max_attempts <= 20:
        raise ValueError("max_attempts must be an integer from 1 through 20")
    if isinstance(base_delay_seconds, bool) or not isinstance(base_delay_seconds, int) or not 1 <= base_delay_seconds <= 3600:
        raise ValueError("base_delay_seconds must be an integer from 1 through 3600")
    connection = _connect(database_path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT attempts, status FROM alert_notification_outbox WHERE id = ?",
            (notification_id,),
        ).fetchone()
        if not row or row["status"] != "sending":
            connection.execute("COMMIT")
            return None
        terminal = row["attempts"] >= max_attempts
        delay = min(base_delay_seconds * (2 ** max(0, row["attempts"] - 1)), 86400)
        next_time = current if terminal else current + timedelta(seconds=delay)
        status = "failed" if terminal else "pending"
        connection.execute(
            """UPDATE alert_notification_outbox
               SET status = ?, updated_at = ?, next_attempt_at = ?, last_error = ?
               WHERE id = ? AND status = 'sending'""",
            (status, current.isoformat(), next_time.isoformat(), error.strip()[:1000], notification_id),
        )
        updated = dict(connection.execute(
            "SELECT * FROM alert_notification_outbox WHERE id = ?", (notification_id,)
        ).fetchone())
        connection.execute("COMMIT")
        return updated
    except Exception:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise
    finally:
        connection.close()
