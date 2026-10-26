"""Offline tests for CIN's durable notification outbox."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest

from cin_alert_outbox import (
    claim_due_notifications,
    enqueue_notification,
    mark_notification_failed,
    mark_notification_sent,
)


NOW = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)


def test_enqueue_is_idempotent_for_same_key(tmp_path):
    path = tmp_path / "alerts.sqlite3"
    first = enqueue_notification(path, idempotency_key="rule-1:event-1", payload={"rule_id": "rule-1"}, now=NOW)
    again = enqueue_notification(path, idempotency_key="rule-1:event-1", payload={"rule_id": "rule-1"}, now=NOW)
    assert first["id"] == again["id"]
    assert first["status"] == "pending"


def test_claim_then_mark_sent(tmp_path):
    path = tmp_path / "alerts.sqlite3"
    enqueue_notification(path, idempotency_key="event-1", payload={"metric": "btc_price"}, now=NOW)
    claimed = claim_due_notifications(path, now=NOW)
    assert len(claimed) == 1
    assert claimed[0]["status"] == "sending"
    assert claimed[0]["attempts"] == 1
    assert claimed[0]["payload"] == {"metric": "btc_price"}
    assert mark_notification_sent(path, notification_id=claimed[0]["id"], now=NOW) is True
    assert mark_notification_sent(path, notification_id=claimed[0]["id"], now=NOW) is False
    assert claim_due_notifications(path, now=NOW) == []


def test_failure_schedules_exponential_retry(tmp_path):
    path = tmp_path / "alerts.sqlite3"
    enqueue_notification(path, idempotency_key="event-1", payload={"a": 1}, now=NOW)
    claimed = claim_due_notifications(path, now=NOW)[0]
    failed = mark_notification_failed(path, notification_id=claimed["id"], error="provider timeout", now=NOW, base_delay_seconds=30)
    assert failed["status"] == "pending"
    assert failed["attempts"] == 1
    assert failed["next_attempt_at"] == (NOW + timedelta(seconds=30)).isoformat()
    assert claim_due_notifications(path, now=NOW) == []
    assert len(claim_due_notifications(path, now=NOW + timedelta(seconds=30))) == 1


def test_max_attempts_moves_to_terminal_failed(tmp_path):
    path = tmp_path / "alerts.sqlite3"
    enqueue_notification(path, idempotency_key="event-1", payload={"a": 1}, now=NOW)
    item = claim_due_notifications(path, now=NOW)[0]
    failed = mark_notification_failed(path, notification_id=item["id"], error="unavailable", now=NOW, max_attempts=1)
    assert failed["status"] == "failed"
    assert claim_due_notifications(path, now=NOW + timedelta(days=1)) == []


def test_duplicate_enqueue_under_concurrency_creates_one_row(tmp_path):
    path = tmp_path / "alerts.sqlite3"
    def enqueue(_):
        return enqueue_notification(path, idempotency_key="same-key", payload={"a": 1}, now=NOW)["id"]
    with ThreadPoolExecutor(max_workers=6) as pool:
        ids = list(pool.map(enqueue, range(6)))
    assert len(set(ids)) == 1


def test_concurrent_claims_do_not_claim_same_pending_row(tmp_path):
    path = tmp_path / "alerts.sqlite3"
    enqueue_notification(path, idempotency_key="event-1", payload={"a": 1}, now=NOW)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: claim_due_notifications(path, now=NOW), range(2)))
    assert sum(len(batch) for batch in results) == 1


@pytest.mark.parametrize("payload", [{"x": float("nan")}, {"x": object()}])
def test_non_json_or_nonfinite_payload_rejected(tmp_path, payload):
    with pytest.raises(ValueError, match="JSON-serializable"):
        enqueue_notification(tmp_path / "alerts.sqlite3", idempotency_key="event-1", payload=payload, now=NOW)


def test_timezone_required_and_error_is_bounded(tmp_path):
    path = tmp_path / "alerts.sqlite3"
    with pytest.raises(ValueError, match="explicit timezone"):
        enqueue_notification(path, idempotency_key="event-1", payload={}, now="2026-10-27T12:00:00")
    enqueue_notification(path, idempotency_key="event-1", payload={}, now=NOW)
    item = claim_due_notifications(path, now=NOW)[0]
    failed = mark_notification_failed(path, notification_id=item["id"], error="x" * 2000, now=NOW)
    assert len(failed["last_error"]) == 1000


def test_abandoned_sending_claim_is_recovered_after_lease(tmp_path):
    path = tmp_path / "alerts.sqlite3"
    enqueue_notification(path, idempotency_key="event-stuck", payload={"a": 1}, now=NOW)
    first = claim_due_notifications(path, now=NOW)[0]
    assert first["attempts"] == 1
    assert claim_due_notifications(path, now=NOW + timedelta(seconds=299)) == []
    recovered = claim_due_notifications(path, now=NOW + timedelta(seconds=300))
    assert len(recovered) == 1
    assert recovered[0]["id"] == first["id"]
    assert recovered[0]["attempts"] == 2


def test_in_memory_path_rejected_because_state_must_survive_calls(tmp_path):
    with pytest.raises(ValueError, match="persistent SQLite file path"):
        enqueue_notification(":memory:", idempotency_key="event-1", payload={}, now=NOW)


def test_invalid_claim_limits_rejected(tmp_path):
    path = tmp_path / "alerts.sqlite3"
    with pytest.raises(ValueError, match="lease_seconds"):
        claim_due_notifications(path, now=NOW, lease_seconds=5)
    with pytest.raises(ValueError, match="limit"):
        claim_due_notifications(path, now=NOW, limit=0)
