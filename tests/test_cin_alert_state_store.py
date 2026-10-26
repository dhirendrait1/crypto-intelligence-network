"""Offline tests for durable CIN alert evaluation state."""
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pytest

from cin_alert_state_store import evaluate_and_record


NOW = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)
RULE = {
    "id": "btc-price-high",
    "metric": "btc_price_usd",
    "operator": "above",
    "threshold": 65000,
    "cooldown_seconds": 300,
}
OBS = {
    "id": "market-event-001",
    "metric": "btc_price_usd",
    "value": 66000,
    "observed_at": "2026-10-27T11:59:00Z",
}


def test_trigger_decision_survives_database_reopen(tmp_path):
    path = tmp_path / "state" / "alerts.sqlite3"
    first = evaluate_and_record(path, RULE, OBS, now=NOW)
    second = evaluate_and_record(
        path, RULE, {**OBS, "id": "market-event-002"}, now=NOW,
    )
    assert first["status"] == "triggered"
    assert second["status"] == "cooldown"
    with sqlite3.connect(path) as connection:
        state = connection.execute(
            "SELECT last_triggered_at FROM alert_rule_state WHERE rule_id = ?",
            (RULE["id"],),
        ).fetchone()
    assert state == (NOW.isoformat(),)


def test_reprocessing_same_observation_never_retriggers(tmp_path):
    path = tmp_path / "alerts.sqlite3"
    first = evaluate_and_record(path, RULE, OBS, now=NOW)
    duplicate = evaluate_and_record(path, RULE, OBS, now=NOW)
    assert first["status"] == "triggered"
    assert duplicate["status"] == "deduplicated"
    assert duplicate["trigger"] is False
    assert duplicate["duplicate_of_status"] == "triggered"


def test_nonmatching_event_is_recorded_and_repeat_is_idempotent(tmp_path):
    path = tmp_path / "alerts.sqlite3"
    observation = {**OBS, "value": 64000}
    first = evaluate_and_record(path, RULE, observation, now=NOW)
    duplicate = evaluate_and_record(path, RULE, observation, now=NOW)
    assert first["status"] == "not_triggered"
    assert duplicate["status"] == "deduplicated"


def test_rules_keep_separate_cooldown_state(tmp_path):
    path = tmp_path / "alerts.sqlite3"
    evaluate_and_record(path, RULE, OBS, now=NOW)
    other_rule = {**RULE, "id": "btc-price-critical", "threshold": 65500}
    result = evaluate_and_record(
        path, other_rule, {**OBS, "id": "market-event-002"}, now=NOW,
    )
    assert result["status"] == "triggered"


def test_invalid_input_is_not_written_as_an_event(tmp_path):
    path = tmp_path / "alerts.sqlite3"
    with pytest.raises(ValueError, match="finite number"):
        evaluate_and_record(path, RULE, {**OBS, "value": float("nan")}, now=NOW)
    with sqlite3.connect(path) as connection:
        count = connection.execute("SELECT COUNT(*) FROM alert_evaluation_events").fetchone()[0]
    assert count == 0


def test_concurrent_duplicate_evaluations_only_trigger_once(tmp_path):
    path = tmp_path / "alerts.sqlite3"
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(
            lambda _: evaluate_and_record(path, RULE, OBS, now=NOW),
            range(6),
        ))
    assert sum(result["trigger"] is True for result in results) == 1
    assert sum(result["status"] == "deduplicated" for result in results) == 5


def test_timezone_is_required_for_evaluation_time(tmp_path):
    with pytest.raises(ValueError, match="explicit timezone"):
        evaluate_and_record(tmp_path / "alerts.sqlite3", RULE, OBS, now="2026-10-27T12:00:00")
