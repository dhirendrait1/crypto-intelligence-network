"""SQLite-backed durable state for CIN's read-only alert evaluator."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from cin_alert_rules import evaluate_alert_rule


_SCHEMA = """
CREATE TABLE IF NOT EXISTS alert_rule_state (
    rule_id TEXT PRIMARY KEY,
    last_triggered_at TEXT
);
CREATE TABLE IF NOT EXISTS alert_evaluation_events (
    rule_id TEXT NOT NULL,
    observation_id TEXT NOT NULL,
    evaluated_at TEXT NOT NULL,
    status TEXT NOT NULL,
    result_json TEXT NOT NULL,
    PRIMARY KEY (rule_id, observation_id)
);
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


def _utc_iso(value: datetime | str) -> str:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("now must be an ISO-8601 timestamp") from exc
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("now must include an explicit timezone")
    return value.astimezone(timezone.utc).isoformat()


def evaluate_and_record(
    database_path: str | Path,
    rule: Mapping[str, Any],
    observation: Mapping[str, Any],
    *,
    now: datetime | str,
    notification_payload: Mapping[str, Any] | None = None,
    notification_channel: str = "default",
) -> dict[str, Any]:
    """Atomically evaluate, persist decision state, and optionally queue delivery.

    If notification_payload is provided and the rule triggers, the evaluation,
    cooldown state, audit event, and outbox row commit in one SQLite transaction.
    The caller still owns scheduling and the external delivery adapter.
    """
    if not isinstance(rule, Mapping) or not isinstance(observation, Mapping):
        raise ValueError("rule and observation must be mappings")
    rule_id, observation_id = rule.get("id"), observation.get("id")
    if not isinstance(rule_id, str) or not rule_id.strip():
        raise ValueError("rule.id must be a non-empty string")
    if not isinstance(observation_id, str) or not observation_id.strip():
        raise ValueError("observation.id must be a non-empty string")
    if notification_payload is not None:
        if not isinstance(notification_payload, Mapping):
            raise ValueError("notification_payload must be a mapping")
        if not isinstance(notification_channel, str) or not notification_channel.strip() or len(notification_channel) > 80:
            raise ValueError("notification_channel must be a non-empty string of at most 80 characters")
        try:
            notification_json = json.dumps(dict(notification_payload), sort_keys=True, separators=(",", ":"), allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise ValueError("notification_payload must be JSON-serializable and contain no non-finite numbers") from exc
    else:
        notification_json = None
    evaluated_at = _utc_iso(now)
    path = str(database_path)
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(path, timeout=10, isolation_level=None) as connection:
        connection.execute("PRAGMA busy_timeout = 10000")
        connection.executescript(_SCHEMA)
        connection.execute("BEGIN IMMEDIATE")
        try:
            prior = connection.execute(
                "SELECT result_json FROM alert_evaluation_events WHERE rule_id = ? AND observation_id = ?",
                (rule_id, observation_id),
            ).fetchone()
            if prior:
                original = json.loads(prior[0])
                duplicate = {
                    **original, "status": "deduplicated",
                    "reason": "observation_already_processed", "trigger": False,
                    "duplicate_of_status": original.get("status"),
                }
                connection.execute("COMMIT")
                return duplicate
            state = connection.execute(
                "SELECT last_triggered_at FROM alert_rule_state WHERE rule_id = ?",
                (rule_id,),
            ).fetchone()
            result = evaluate_alert_rule(
                rule, observation, now=evaluated_at,
                last_triggered_at=state[0] if state else None,
            )
            if result["status"] == "triggered":
                connection.execute(
                    """INSERT INTO alert_rule_state (rule_id, last_triggered_at)
                       VALUES (?, ?)
                       ON CONFLICT(rule_id) DO UPDATE SET last_triggered_at = excluded.last_triggered_at""",
                    (rule_id, evaluated_at),
                )
                if notification_json is not None:
                    idempotency_key = f"{rule_id}:{observation_id}:{notification_channel}"
                    connection.execute(
                        """INSERT INTO alert_notification_outbox
                           (idempotency_key, payload_json, status, attempts, created_at, updated_at, next_attempt_at)
                           VALUES (?, ?, 'pending', 0, ?, ?, ?)
                           ON CONFLICT(idempotency_key) DO NOTHING""",
                        (idempotency_key, notification_json, evaluated_at, evaluated_at, evaluated_at),
                    )
                    outbox_row = connection.execute(
                        "SELECT id FROM alert_notification_outbox WHERE idempotency_key = ?",
                        (idempotency_key,),
                    ).fetchone()
                    result = {**result, "notification_enqueued": True, "notification_outbox_id": outbox_row[0]}
            connection.execute(
                """INSERT INTO alert_evaluation_events
                   (rule_id, observation_id, evaluated_at, status, result_json)
                   VALUES (?, ?, ?, ?, ?)""",
                (rule_id, observation_id, evaluated_at, result["status"], json.dumps(result, sort_keys=True)),
            )
            connection.execute("COMMIT")
            return result
        except Exception:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
