"""Offline regression tests for deterministic CIN alert-rule evaluation."""
from datetime import datetime, timedelta, timezone

import pytest

from cin_alert_rules import evaluate_alert_rule


NOW = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)
RULE = {
    "id": "btc-price-high",
    "metric": "btc_price_usd",
    "operator": "above",
    "threshold": 65000,
    "cooldown_seconds": 300,
}
OBSERVATION = {
    "id": "market-snapshot-001",
    "metric": "btc_price_usd",
    "value": 65100,
    "observed_at": "2026-10-27T11:59:30Z",
}


def test_matching_threshold_triggers_once_and_is_auditable():
    result = evaluate_alert_rule(RULE, OBSERVATION, now=NOW)
    assert result["status"] == "triggered"
    assert result["trigger"] is True
    assert result["matched"] is True
    assert result["rule_id"] == RULE["id"]
    assert result["observation_id"] == OBSERVATION["id"]
    assert result["evaluated_at"] == NOW.isoformat()


def test_non_matching_threshold_does_not_trigger():
    result = evaluate_alert_rule(
        {**RULE, "operator": "below", "threshold": 65000},
        {**OBSERVATION, "value": 65000},
        now=NOW,
    )
    assert result["status"] == "not_triggered"
    assert result["trigger"] is False
    assert result["reason"] == "threshold_not_crossed"


def test_repeated_observation_is_deduplicated_before_cooldown():
    result = evaluate_alert_rule(
        RULE, OBSERVATION, now=NOW,
        last_triggered_at=NOW - timedelta(seconds=10),
        last_event_id=OBSERVATION["id"],
    )
    assert result["status"] == "deduplicated"
    assert result["trigger"] is False


def test_matching_new_observation_is_suppressed_during_cooldown():
    result = evaluate_alert_rule(
        RULE, {**OBSERVATION, "id": "market-snapshot-002"}, now=NOW,
        last_triggered_at=NOW - timedelta(seconds=100),
    )
    assert result["status"] == "cooldown"
    assert result["cooldown_remaining_seconds"] == 200
    assert result["trigger"] is False


def test_alert_can_trigger_after_cooldown_expires():
    result = evaluate_alert_rule(
        RULE, {**OBSERVATION, "id": "market-snapshot-003"}, now=NOW,
        last_triggered_at=NOW - timedelta(seconds=300),
    )
    assert result["status"] == "triggered"
    assert result["trigger"] is True


@pytest.mark.parametrize("value", [True, float("nan"), float("inf"), float("-inf"), "65001"])
def test_invalid_numeric_observations_are_rejected(value):
    with pytest.raises(ValueError, match="observation.value must be a finite number"):
        evaluate_alert_rule(RULE, {**OBSERVATION, "value": value}, now=NOW)


@pytest.mark.parametrize(
    "rule, observation, now, message",
    [
        ({**RULE, "operator": "equal"}, OBSERVATION, NOW, "rule.operator"),
        ({**RULE, "cooldown_seconds": True}, OBSERVATION, NOW, "cooldown_seconds"),
        (RULE, {**OBSERVATION, "metric": "eth_price_usd"}, NOW, "must match"),
        (RULE, {**OBSERVATION, "observed_at": "2026-10-27T11:59:30"}, NOW, "explicit timezone"),
        (RULE, {**OBSERVATION, "observed_at": "2026-10-27T12:01:00Z"}, NOW, "cannot be in the future"),
        (RULE, OBSERVATION, "2026-10-27T12:00:00", "explicit timezone"),
    ],
)
def test_invalid_rule_or_observation_contract_is_rejected(rule, observation, now, message):
    with pytest.raises(ValueError, match=message):
        evaluate_alert_rule(rule, observation, now=now)


def test_cooldown_timestamp_in_future_is_rejected():
    with pytest.raises(ValueError, match="last_triggered_at cannot be in the future"):
        evaluate_alert_rule(
            RULE, OBSERVATION, now=NOW,
            last_triggered_at=NOW + timedelta(seconds=1),
        )


def test_missing_optional_cooldown_defaults_to_zero():
    rule = {key: value for key, value in RULE.items() if key != "cooldown_seconds"}
    result = evaluate_alert_rule(
        rule, {**OBSERVATION, "id": "market-snapshot-004"}, now=NOW,
        last_triggered_at=NOW - timedelta(seconds=1),
    )
    assert result["status"] == "triggered"
