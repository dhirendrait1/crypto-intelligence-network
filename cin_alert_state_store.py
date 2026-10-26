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
) -> dict[str, Any]:
    """Atomically evaluate and record a unique rule/observation pair.

    The caller invokes this function when an observation is available. This
    function does not poll sources, schedule work, or deliver notifications.
    """
    if not isinstance(rule, Mapping) or not isinstance(observation, Mapping):
        raise ValueError("rule and observation must be mappings")
    rule_id, observation_id = rule.get("id"), observation.get("id")
    if not isinstance(rule_id, str) or not rule_id.strip():
        raise ValueError("rule.id must be a non-empty string")
    if not isinstance(observation_id, str) or not observation_id.strip():
        raise ValueError("observation.id must be a non-empty string")
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
