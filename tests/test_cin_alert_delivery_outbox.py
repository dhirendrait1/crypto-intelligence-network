"""Offline tests for CIN's durable notification outbox state machine."""
from concurrent.futures import ThreadPoolExecutor
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from cin_alert_delivery_outbox import (
    claim_due_alerts,
    enqueue_alert_delivery,
    mark_alert_failed,
    mark_alert_sent,
    list_uncertain_alert_deliveries,
    resolve_uncertain_alert_delivery,
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


def test_abandoned_worker_lease_becomes_uncertain_not_reclaimed(tmp_path):
    path = tmp_path / "alerts.sqlite3"
    item = enqueue_alert_delivery(path, rule_id="r1", observation_id="stuck", payload={"v": 1}, now=NOW)
    first = claim_due_alerts(path, now=NOW)[0]
    assert first["attempts"] == 1
    assert claim_due_alerts(path, now=NOW + timedelta(seconds=299)) == []
    assert claim_due_alerts(path, now=NOW + timedelta(seconds=300)) == []
    uncertain = list_uncertain_alert_deliveries(path)
    assert len(uncertain) == 1
    assert uncertain[0]["idempotency_key"] == item["idempotency_key"]
    assert uncertain[0]["status"] == "uncertain"
    assert uncertain[0]["attempts"] == 1


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


def test_stale_worker_cannot_acknowledge_after_expired_lease_becomes_uncertain(tmp_path):
    path = tmp_path / "alerts.sqlite3"
    item = enqueue_alert_delivery(path, rule_id="r1", observation_id="stale", payload={"v": 1}, now=NOW)
    old_claim = claim_due_alerts(path, now=NOW, lease_seconds=300)[0]
    assert old_claim["status"] == "sending"
    assert claim_due_alerts(path, now=NOW + timedelta(seconds=300), lease_seconds=300) == []
    uncertain = list_uncertain_alert_deliveries(path)
    assert len(uncertain) == 1
    assert uncertain[0]["idempotency_key"] == item["idempotency_key"]
    with pytest.raises(ValueError, match="sending state"):
        mark_alert_sent(path, item["idempotency_key"], now=NOW + timedelta(seconds=301), claim_attempt=old_claim["attempts"])
    with pytest.raises(ValueError, match="sending state"):
        mark_alert_failed(path, item["idempotency_key"], now=NOW + timedelta(seconds=301), error_code="stale_worker", claim_attempt=old_claim["attempts"])



def test_expired_lease_becomes_uncertain_and_is_not_automatically_retried(tmp_path):
    path = tmp_path / "alerts.sqlite3"
    item = enqueue_alert_delivery(path, rule_id="r1", observation_id="uncertain", payload={"text": "alert"}, now=NOW)
    claim_due_alerts(path, now=NOW, lease_seconds=300)
    assert claim_due_alerts(path, now=NOW + timedelta(seconds=300), lease_seconds=300) == []
    uncertain = list_uncertain_alert_deliveries(path)
    assert len(uncertain) == 1
    assert uncertain[0]["idempotency_key"] == item["idempotency_key"]
    assert uncertain[0]["status"] == "uncertain"
    assert uncertain[0]["last_error_code"] == "delivery_outcome_unknown"
    assert claim_due_alerts(path, now=NOW + timedelta(days=1), lease_seconds=300) == []


def test_operator_can_resolve_uncertain_as_sent_or_authorize_retry(tmp_path):
    path = tmp_path / "alerts.sqlite3"
    sent_item = enqueue_alert_delivery(path, rule_id="r1", observation_id="sent", payload={}, now=NOW)
    retry_item = enqueue_alert_delivery(path, rule_id="r1", observation_id="retry", payload={}, now=NOW)
    claim_due_alerts(path, now=NOW, limit=2, lease_seconds=300)
    claim_due_alerts(path, now=NOW + timedelta(seconds=300), limit=2, lease_seconds=300)

    resolved_sent = resolve_uncertain_alert_delivery(path, sent_item["idempotency_key"], resolution="sent", now=NOW + timedelta(seconds=301))
    assert resolved_sent["status"] == "sent"
    resolved_retry = resolve_uncertain_alert_delivery(path, retry_item["idempotency_key"], resolution="retry_authorized", now=NOW + timedelta(seconds=301))
    assert resolved_retry["status"] == "pending"
    assert resolved_retry["last_error_code"] == "operator_authorized_retry_duplicate_risk"
    assert claim_due_alerts(path, now=NOW + timedelta(seconds=302), limit=2)[0]["status"] == "sending"


def test_uncertain_resolution_rejects_invalid_or_repeated_resolution(tmp_path):
    path = tmp_path / "alerts.sqlite3"
    item = enqueue_alert_delivery(path, rule_id="r1", observation_id="resolve", payload={}, now=NOW)
    claim_due_alerts(path, now=NOW)
    claim_due_alerts(path, now=NOW + timedelta(seconds=300))
    with pytest.raises(ValueError):
        resolve_uncertain_alert_delivery(path, item["idempotency_key"], resolution="maybe", now=NOW)
    resolve_uncertain_alert_delivery(path, item["idempotency_key"], resolution="sent", now=NOW)
    with pytest.raises(ValueError):
        resolve_uncertain_alert_delivery(path, item["idempotency_key"], resolution="sent", now=NOW)


def test_legacy_database_migrates_status_constraint_and_preserves_rows(tmp_path):
    path = tmp_path / "legacy-alerts.sqlite3"
    legacy_schema = """
    CREATE TABLE alert_delivery_outbox (
        idempotency_key TEXT PRIMARY KEY,
        rule_id TEXT NOT NULL,
        observation_id TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('pending','sending','sent','failed','dead')),
        attempts INTEGER NOT NULL DEFAULT 0,
        next_attempt_at TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        last_error_code TEXT
    );
    CREATE INDEX idx_alert_outbox_due ON alert_delivery_outbox(status, next_attempt_at);
    """
    with sqlite3.connect(path) as db:
        db.executescript(legacy_schema)
        timestamp = NOW.isoformat()
        db.execute(
            """INSERT INTO alert_delivery_outbox
            (idempotency_key,rule_id,observation_id,payload_json,status,attempts,
             next_attempt_at,created_at,updated_at,last_error_code)
            VALUES (?,?,?,?,?,?,?,?,?,?)""",
            ("r1:legacy", "r1", "legacy", '{"text":"keep me"}', "sending", 1,
             timestamp, timestamp, timestamp, None),
        )

    # Opening through the current implementation migrates the legacy CHECK
    # constraint without dropping existing outbox records.
    assert claim_due_alerts(path, now=NOW + timedelta(seconds=300)) == []
    uncertain = list_uncertain_alert_deliveries(path)
    assert len(uncertain) == 1
    assert uncertain[0]["idempotency_key"] == "r1:legacy"
    assert uncertain[0]["payload"] == {"text": "keep me"}
    assert uncertain[0]["status"] == "uncertain"
    with sqlite3.connect(path) as db:
        schema = db.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='alert_delivery_outbox'"
        ).fetchone()[0]
        assert "uncertain" in schema
        assert "CHECK (attempts >= 0)" in schema
        assert db.execute("SELECT COUNT(*) FROM alert_delivery_outbox").fetchone()[0] == 1
        indexes = {
            row[0] for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='alert_delivery_outbox'"
            )
        }
        assert "idx_alert_outbox_due" in indexes
        assert "idx_alert_delivery_outbox_due" in indexes
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                """INSERT INTO alert_delivery_outbox
                (idempotency_key,rule_id,observation_id,payload_json,status,attempts,
                 next_attempt_at,created_at,updated_at,last_error_code)
                VALUES ('invalid:attempts','invalid','attempts','{}','pending',-1,?,?,?,NULL)""",
                (timestamp, timestamp, timestamp),
            )


def test_uncertain_lease_overwrites_prior_failure_code_with_unknown_outcome(tmp_path):
    path = tmp_path / "alerts.sqlite3"
    item = enqueue_alert_delivery(
        path, rule_id="r1", observation_id="prior-failure",
        payload={"text": "alert"}, now=NOW,
    )
    claim_due_alerts(path, now=NOW)
    failed = mark_alert_failed(
        path, item["idempotency_key"], now=NOW,
        error_code="telegram_network_error", retry_delay_seconds=1, claim_attempt=1,
    )
    assert failed["last_error_code"] == "telegram_network_error"
    second_claim = claim_due_alerts(path, now=NOW + timedelta(seconds=1))[0]
    assert second_claim["attempts"] == 2

    assert claim_due_alerts(path, now=NOW + timedelta(seconds=301)) == []
    uncertain = list_uncertain_alert_deliveries(path)
    assert len(uncertain) == 1
    assert uncertain[0]["last_error_code"] == "delivery_outcome_unknown"


def test_intermediate_schema_with_uncertain_but_unconstrained_attempts_is_migrated(tmp_path):
    path = tmp_path / "intermediate-alerts.sqlite3"
    timestamp = NOW.isoformat()
    intermediate_schema = """
    CREATE TABLE alert_delivery_outbox (
        idempotency_key TEXT PRIMARY KEY,
        rule_id TEXT NOT NULL,
        observation_id TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('pending','sending','sent','failed','dead','uncertain')),
        attempts INTEGER NOT NULL DEFAULT 0,
        next_attempt_at TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        last_error_code TEXT
    );
    CREATE INDEX idx_alert_outbox_due ON alert_delivery_outbox(status, next_attempt_at);
    """
    with sqlite3.connect(path) as db:
        db.executescript(intermediate_schema)
        db.execute(
            """INSERT INTO alert_delivery_outbox
            (idempotency_key,rule_id,observation_id,payload_json,status,attempts,
             next_attempt_at,created_at,updated_at,last_error_code)
            VALUES (?,?,?,?,?,?,?,?,?,?)""",
            ("r1:intermediate", "r1", "intermediate", '{"text":"preserve"}',
             "uncertain", 1, timestamp, timestamp, timestamp, "delivery_outcome_unknown"),
        )

    uncertain = list_uncertain_alert_deliveries(path)
    assert len(uncertain) == 1
    assert uncertain[0]["idempotency_key"] == "r1:intermediate"
    with sqlite3.connect(path) as db:
        schema = db.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='alert_delivery_outbox'"
        ).fetchone()[0]
        assert "CHECK (attempts >= 0)" in schema
        assert db.execute("SELECT COUNT(*) FROM alert_delivery_outbox").fetchone()[0] == 1
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                """INSERT INTO alert_delivery_outbox
                (idempotency_key,rule_id,observation_id,payload_json,status,attempts,
                 next_attempt_at,created_at,updated_at,last_error_code)
                VALUES ('invalid:negative','invalid','negative','{}','pending',-1,?,?,?,NULL)""",
                (timestamp, timestamp, timestamp),
            )


def test_concurrent_workers_never_claim_the_same_pending_item(tmp_path):
    path = tmp_path / "concurrent-claims.sqlite3"
    for i in range(12):
        enqueue_alert_delivery(
            path, rule_id="concurrent", observation_id=f"event-{i}",
            payload={"event": i}, now=NOW,
        )

    def claim_batch(_):
        return claim_due_alerts(path, now=NOW, limit=12)

    with ThreadPoolExecutor(max_workers=6) as pool:
        batches = list(pool.map(claim_batch, range(6)))

    claimed = [item for batch in batches for item in batch]
    keys = [item["idempotency_key"] for item in claimed]
    assert len(claimed) == 12
    assert len(set(keys)) == 12
    assert all(item["status"] == "sending" and item["attempts"] == 1 for item in claimed)
    assert claim_due_alerts(path, now=NOW, limit=12) == []


@pytest.mark.parametrize("lease_seconds", [True, False, "300", 1.5, None, 29, 3601])
def test_claim_rejects_invalid_lease_seconds_before_time_arithmetic(tmp_path, lease_seconds):
    path = tmp_path / "invalid-lease.sqlite3"
    enqueue_alert_delivery(path, rule_id="r1", observation_id="e1", payload={"value": 1}, now=NOW)
    with pytest.raises(ValueError, match="lease_seconds"):
        claim_due_alerts(path, now=NOW, lease_seconds=lease_seconds)


def test_previous_claim_cannot_acknowledge_after_retry_is_reclaimed(tmp_path):
    path = tmp_path / "attempt-fencing.sqlite3"
    item = enqueue_alert_delivery(
        path, rule_id="r1", observation_id="fenced", payload={"value": 1}, now=NOW,
    )
    first = claim_due_alerts(path, now=NOW)[0]
    failed = mark_alert_failed(
        path, item["idempotency_key"], now=NOW,
        error_code="provider_timeout", retry_delay_seconds=1,
        claim_attempt=first["attempts"],
    )
    assert failed["status"] == "failed"
    second = claim_due_alerts(path, now=NOW + timedelta(seconds=2))[0]
    assert second["attempts"] == first["attempts"] + 1
    with pytest.raises(ValueError, match="sending state"):
        mark_alert_sent(
            path, item["idempotency_key"], now=NOW + timedelta(seconds=3),
            claim_attempt=first["attempts"],
        )
    accepted = mark_alert_sent(
        path, item["idempotency_key"], now=NOW + timedelta(seconds=3),
        claim_attempt=second["attempts"],
    )
    assert accepted["status"] == "sent"
    assert accepted["attempts"] == 2


@pytest.mark.parametrize("claim_attempt", [True, False, "1", 1.5, 0, -1, None])
def test_sent_rejects_invalid_claim_attempt_identifier(tmp_path, claim_attempt):
    path = tmp_path / "invalid-sent-claim.sqlite3"
    item = enqueue_alert_delivery(
        path, rule_id="r1", observation_id="sent-invalid", payload={}, now=NOW,
    )
    claim_due_alerts(path, now=NOW)
    with pytest.raises(ValueError, match="claim_attempt"):
        mark_alert_sent(
            path, item["idempotency_key"], now=NOW,
            claim_attempt=claim_attempt,
        )


@pytest.mark.parametrize("claim_attempt", [True, False, "1", 1.5, 0, -1, None])
def test_failure_rejects_invalid_claim_attempt_identifier(tmp_path, claim_attempt):
    path = tmp_path / "invalid-failed-claim.sqlite3"
    item = enqueue_alert_delivery(
        path, rule_id="r1", observation_id="failed-invalid", payload={}, now=NOW,
    )
    claim_due_alerts(path, now=NOW)
    with pytest.raises(ValueError, match="claim_attempt"):
        mark_alert_failed(
            path, item["idempotency_key"], now=NOW,
            error_code="provider_timeout", claim_attempt=claim_attempt,
        )
