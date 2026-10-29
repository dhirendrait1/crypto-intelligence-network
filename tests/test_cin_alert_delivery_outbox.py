"""Offline tests for CIN's durable notification outbox state machine."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest

from cin_alert_delivery_outbox import (
    claim_due_alerts,
    enqueue_alert_delivery,
    mark_alert_failed,
    mark_alert_sent,
)

NOW = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)


def test_enqueue_is_idempotent_and_does_not_store_duplicate_payloads(tmp_path):
    path = tmp_path / "alerts.sqlite3"
    first = enqueue_alert_delivery(path, rule_id="r1", observation_id="e1", payload={"metric": "btc", "value": 1}, now=NOW)
    second = enqueue_alert_delivery(path, rule_id="r1", observation_id="e1", payload={"metric": "btc", "value": 2}, now=NOW)
    assert first["status"] == "pending"
    assert second["idempotency_key"] == first["idempotency_key"]
    assert second["payload"] == first["payload"]


def test_claim_and_successful_delivery_state_transitions(tmp_path):
    path = tmp_path / "alerts.sqlite3"
    item = enqueue_alert_delivery(path, rule_id="r1", observation_id="e1", payload={"value": 1}, now=NOW)
    claimed = claim_due_alerts(path, now=NOW)
    assert len(claimed) == 1
    assert claimed[0]["status"] == "sending"
    assert claim_due_alerts(path, now=NOW) == []
    sent = mark_alert_sent(path, item["idempotency_key"], now=NOW + timedelta(seconds=1), claim_attempt=claimed[0]["attempts"])
    assert sent["status"] == "sent"
    assert sent["attempts"] == 1
    assert claim_due_alerts(path, now=NOW + timedelta(days=1)) == []


def test_failure_uses_bounded_exponential_backoff_and_can_retry(tmp_path):
    path = tmp_path / "alerts.sqlite3"
    item = enqueue_alert_delivery(path, rule_id="r1", observation_id="e1", payload={"value": 1}, now=NOW)
    claim_due_alerts(path, now=NOW)
    failed = mark_alert_failed(path, item["idempotency_key"], now=NOW, error_code="provider_timeout", retry_delay_seconds=30, claim_attempt=1)
    assert failed["status"] == "failed"
    assert failed["attempts"] == 1
    assert failed["next_attempt_at"] == (NOW + timedelta(seconds=30)).isoformat()
    assert claim_due_alerts(path, now=NOW + timedelta(seconds=29)) == []
    assert claim_due_alerts(path, now=NOW + timedelta(seconds=30))[0]["status"] == "sending"


def test_retry_exhaustion_moves_to_dead_letter_and_never_claims_again(tmp_path):
    path = tmp_path / "alerts.sqlite3"
    item = enqueue_alert_delivery(path, rule_id="r1", observation_id="e1", payload={}, now=NOW)
    claim_due_alerts(path, now=NOW)
    dead = mark_alert_failed(path, item["idempotency_key"], now=NOW, error_code="timeout", max_attempts=1, claim_attempt=1)
    assert dead["status"] == "dead"
    assert claim_due_alerts(path, now=NOW + timedelta(days=2)) == []


def test_concurrent_enqueue_creates_one_idempotency_key(tmp_path):
    path = tmp_path / "alerts.sqlite3"
    def add(_):
        return enqueue_alert_delivery(path, rule_id="r1", observation_id="e1", payload={"value": 1}, now=NOW)
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(add, range(6)))
    assert {result["idempotency_key"] for result in results} == {"r1:e1"}
    assert {result["status"] for result in results} == {"pending"}


@pytest.mark.parametrize("bad_payload", [{"v": float("nan")}, {"v": float("inf")}])
def test_non_json_finite_payloads_are_rejected(tmp_path, bad_payload):
    with pytest.raises(ValueError):
        enqueue_alert_delivery(tmp_path / "alerts.sqlite3", rule_id="r1", observation_id="e1", payload=bad_payload, now=NOW)


def test_invalid_time_and_retry_limits_are_rejected(tmp_path):
    path = tmp_path / "alerts.sqlite3"
    with pytest.raises(ValueError, match="explicit timezone"):
        enqueue_alert_delivery(path, rule_id="r1", observation_id="e1", payload={}, now="2026-10-27T12:00:00")
    with pytest.raises(ValueError, match="limit"):
        claim_due_alerts(path, now=NOW, limit=True)


def test_abandoned_worker_lease_is_reclaimed(tmp_path):
    path = tmp_path / "alerts.sqlite3"
    item = enqueue_alert_delivery(path, rule_id="r1", observation_id="stuck", payload={"v": 1}, now=NOW)
    first = claim_due_alerts(path, now=NOW)[0]
    assert first["attempts"] == 1
    assert claim_due_alerts(path, now=NOW + timedelta(seconds=299)) == []
    recovered = claim_due_alerts(path, now=NOW + timedelta(seconds=300))
    assert len(recovered) == 1
    assert recovered[0]["idempotency_key"] == item["idempotency_key"]
    assert recovered[0]["attempts"] == 2


def test_expired_lease_at_attempt_limit_moves_to_dead_letter(tmp_path):
    path = tmp_path / "alerts.sqlite3"
    enqueue_alert_delivery(path, rule_id="r1", observation_id="stuck", payload={}, now=NOW)
    claim_due_alerts(path, now=NOW, max_attempts=1)
    assert claim_due_alerts(path, now=NOW + timedelta(seconds=300), max_attempts=1) == []
    with __import__("sqlite3").connect(path) as db:
        assert db.execute("SELECT status FROM alert_delivery_outbox").fetchone()[0] == "dead"


def test_in_memory_path_rejected(tmp_path):
    with pytest.raises(ValueError, match="persistent SQLite file path"):
        enqueue_alert_delivery(":memory:", rule_id="r1", observation_id="e1", payload={}, now=NOW)


def test_stale_worker_cannot_mark_reclaimed_attempt_sent_or_failed(tmp_path):
    path = tmp_path / "alerts.sqlite3"
    item = enqueue_alert_delivery(path, rule_id="r1", observation_id="stale", payload={"v": 1}, now=NOW)
    old_claim = claim_due_alerts(path, now=NOW, lease_seconds=300)[0]
    new_claim = claim_due_alerts(path, now=NOW + timedelta(seconds=300), lease_seconds=300)[0]
    assert new_claim["attempts"] == old_claim["attempts"] + 1
    with pytest.raises(ValueError, match="sending state"):
        mark_alert_sent(path, item["idempotency_key"], now=NOW + timedelta(seconds=301), claim_attempt=old_claim["attempts"])
    with pytest.raises(ValueError, match="sending state"):
        mark_alert_failed(path, item["idempotency_key"], now=NOW + timedelta(seconds=301), error_code="stale_worker", claim_attempt=old_claim["attempts"])
    current = mark_alert_sent(path, item["idempotency_key"], now=NOW + timedelta(seconds=302), claim_attempt=new_claim["attempts"])
    assert current["status"] == "sent"
