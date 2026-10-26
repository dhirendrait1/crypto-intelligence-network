"""Offline regression tests for CIN alert evaluation and persistence."""
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest

from cin_alert_rules import evaluate_alert_rule
from cin_alert_state_store import evaluate_and_record


NOW = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)
RULE = {"id": "btc-price-high", "metric": "btc_price_usd", "operator": "above", "threshold": 65000, "cooldown_seconds": 300}
OBS = {"id": "market-event-001", "metric": "btc_price_usd", "value": 66000, "observed_at": "2026-10-27T11:59:00Z"}


def test_threshold_evaluation_is_auditable_and_deterministic():
    result = evaluate_alert_rule(RULE, OBS, now=NOW)
    assert result["status"] == "triggered"
    assert result["trigger"] is True
    assert result["rule_id"] == RULE["id"]
    assert result["observation_id"] == OBS["id"]
    assert result["evaluated_at"] == NOW.isoformat()


def test_threshold_equality_does_not_trigger():
    result = evaluate_alert_rule({**RULE, "operator": "below"}, {**OBS, "value": 65000}, now=NOW)
    assert result["status"] == "not_triggered"
    assert result["trigger"] is False


def test_in_memory_deduplication_and_cooldown_contract():
    duplicate = evaluate_alert_rule(RULE, OBS, now=NOW, last_event_id=OBS["id"])
    assert duplicate["status"] == "deduplicated"
    cooldown = evaluate_alert_rule(RULE, {**OBS, "id": "event-2"}, now=NOW, last_triggered_at=NOW-timedelta(seconds=100))
    assert cooldown["status"] == "cooldown"
    assert cooldown["cooldown_remaining_seconds"] == 200


@pytest.mark.parametrize("value", [True, float("nan"), float("inf"), float("-inf"), "66000"])
def test_invalid_numeric_observation_rejected(value):
    with pytest.raises(ValueError, match="observation.value must be a finite number"):
        evaluate_alert_rule(RULE, {**OBS, "value": value}, now=NOW)


@pytest.mark.parametrize(
    "rule, observation, now, message",
    [
        ({**RULE, "operator": "equal"}, OBS, NOW, "rule.operator"),
        ({**RULE, "cooldown_seconds": True}, OBS, NOW, "cooldown_seconds"),
        (RULE, {**OBS, "metric": "eth_price_usd"}, NOW, "must match"),
        (RULE, {**OBS, "observed_at": "2026-10-27T11:59:00"}, NOW, "explicit timezone"),
        (RULE, {**OBS, "observed_at": "2026-10-27T12:01:00Z"}, NOW, "cannot be in the future"),
        (RULE, OBS, "2026-10-27T12:00:00", "explicit timezone"),
    ],
)
def test_invalid_contracts_rejected(rule, observation, now, message):
    with pytest.raises(ValueError, match=message):
        evaluate_alert_rule(rule, observation, now=now)


def test_future_last_trigger_rejected():
    with pytest.raises(ValueError, match="last_triggered_at cannot be in the future"):
        evaluate_alert_rule(RULE, OBS, now=NOW, last_triggered_at=NOW+timedelta(seconds=1))


def test_persistent_cooldown_survives_database_reopen(tmp_path):
    path = tmp_path / "state" / "alerts.sqlite3"
    first = evaluate_and_record(path, RULE, OBS, now=NOW)
    second = evaluate_and_record(path, RULE, {**OBS, "id": "market-event-002"}, now=NOW)
    assert first["status"] == "triggered"
    assert second["status"] == "cooldown"
    with sqlite3.connect(path) as db:
        state = db.execute("SELECT last_triggered_at FROM alert_rule_state WHERE rule_id=?", (RULE["id"],)).fetchone()
    assert state == (NOW.isoformat(),)


def test_duplicate_observation_is_never_retriggered(tmp_path):
    path = tmp_path / "alerts.sqlite3"
    assert evaluate_and_record(path, RULE, OBS, now=NOW)["status"] == "triggered"
    duplicate = evaluate_and_record(path, RULE, OBS, now=NOW)
    assert duplicate["status"] == "deduplicated"
    assert duplicate["trigger"] is False
    assert duplicate["duplicate_of_status"] == "triggered"


def test_nonmatching_observation_is_idempotently_recorded(tmp_path):
    path = tmp_path / "alerts.sqlite3"
    observation = {**OBS, "value": 64000}
    assert evaluate_and_record(path, RULE, observation, now=NOW)["status"] == "not_triggered"
    assert evaluate_and_record(path, RULE, observation, now=NOW)["status"] == "deduplicated"


def test_different_rules_have_independent_cooldowns(tmp_path):
    path = tmp_path / "alerts.sqlite3"
    evaluate_and_record(path, RULE, OBS, now=NOW)
    other = {**RULE, "id": "btc-price-critical", "threshold": 65500}
    assert evaluate_and_record(path, other, {**OBS, "id": "market-event-002"}, now=NOW)["status"] == "triggered"


def test_invalid_event_is_not_persisted(tmp_path):
    path = tmp_path / "alerts.sqlite3"
    with pytest.raises(ValueError, match="finite number"):
        evaluate_and_record(path, RULE, {**OBS, "value": float("nan")}, now=NOW)
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT COUNT(*) FROM alert_evaluation_events").fetchone()[0] == 0


def test_concurrent_duplicate_event_triggers_once(tmp_path):
    path = tmp_path / "alerts.sqlite3"
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda _: evaluate_and_record(path, RULE, OBS, now=NOW), range(6)))
    assert sum(result["trigger"] is True for result in results) == 1
    assert sum(result["status"] == "deduplicated" for result in results) == 5


def test_persistent_store_requires_timezone_aware_now(tmp_path):
    with pytest.raises(ValueError, match="explicit timezone"):
        evaluate_and_record(tmp_path / "alerts.sqlite3", RULE, OBS, now="2026-10-27T12:00:00")


def test_trigger_and_notification_enqueue_are_atomic_and_idempotent(tmp_path):
    path = tmp_path / "alerts.sqlite3"
    result = evaluate_and_record(
        path, RULE, OBS, now=NOW,
        notification_payload={"channel": "test", "message": "BTC threshold crossed"},
        notification_channel="test",
    )
    assert result["status"] == "triggered"
    assert result["notification_enqueued"] is True
    assert result["notification_idempotency_key"] == f'{RULE["id"]}:{OBS["id"]}'
    with sqlite3.connect(path) as db:
        events = db.execute("SELECT COUNT(*) FROM alert_evaluation_events").fetchone()[0]
        queued = db.execute("SELECT COUNT(*) FROM alert_delivery_outbox").fetchone()[0]
        status = db.execute("SELECT status FROM alert_delivery_outbox").fetchone()[0]
    assert (events, queued, status) == (1, 1, "pending")
    duplicate = evaluate_and_record(
        path, RULE, OBS, now=NOW,
        notification_payload={"channel": "test", "message": "duplicate"},
        notification_channel="test",
    )
    assert duplicate["status"] == "deduplicated"
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT COUNT(*) FROM alert_delivery_outbox").fetchone()[0] == 1


def test_nonmatching_rule_does_not_enqueue_notification(tmp_path):
    path = tmp_path / "alerts.sqlite3"
    result = evaluate_and_record(
        path, RULE, {**OBS, "value": 64000}, now=NOW,
        notification_payload={"message": "should not queue"},
    )
    assert result["status"] == "not_triggered"
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT COUNT(*) FROM alert_delivery_outbox").fetchone()[0] == 0


def test_invalid_notification_payload_fails_before_state_is_changed(tmp_path):
    path = tmp_path / "alerts.sqlite3"
    with pytest.raises(ValueError, match="JSON-serializable"):
        evaluate_and_record(path, RULE, OBS, now=NOW, notification_payload={"bad": float("nan")})
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT COUNT(*) FROM alert_evaluation_events").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM alert_rule_state").fetchone()[0] == 0
