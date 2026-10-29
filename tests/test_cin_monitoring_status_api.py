from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest

from cin_monitoring_status_api import MonitoringSnapshot, monitoring_status


def test_fully_healthy_snapshot_is_healthy_but_does_not_claim_live_checks():
    result = monitoring_status(MonitoringSnapshot(
        health="healthy", readiness="ready", provider_status="healthy",
        freshness="fresh", observed_at="2026-10-28T00:00:00Z",
    ))
    assert result["status"] == "healthy"
    assert result["read_only"] is True
    assert result["checks_performed"] is False


@pytest.mark.parametrize("kwargs", [
    {"readiness": "not_ready"},
    {"provider_status": "unavailable"},
    {"health": "unavailable"},
])
def test_unavailable_inputs_take_precedence(kwargs):
    base = {"health": "healthy", "readiness": "ready",
            "provider_status": "healthy", "freshness": "fresh"}
    base.update(kwargs)
    assert monitoring_status(MonitoringSnapshot(**base))["status"] == "unavailable"


def test_stale_data_is_degraded_not_healthy():
    result = monitoring_status(MonitoringSnapshot(
        health="healthy", readiness="ready", provider_status="healthy",
        freshness="stale", warnings=["provider timestamp is old"],
    ))
    assert result["status"] == "degraded"
    assert result["warnings"] == ["provider timestamp is old"]


def test_missing_evidence_remains_unknown():
    result = monitoring_status(MonitoringSnapshot())
    assert result["status"] == "unknown"
    assert result["observed_at"] is None


def test_unknown_enum_value_is_rejected():
    with pytest.raises(ValidationError):
        MonitoringSnapshot(provider_status="probably-fine")


def test_http_route_returns_explicit_caller_supplied_status_contract():
    app = FastAPI()
    from cin_monitoring_status_api import router
    app.include_router(router)
    response = TestClient(app).post("/monitoring/status", json={
        "health": "healthy", "readiness": "ready",
        "provider_status": "healthy", "freshness": "fresh",
        "observed_at": "2026-10-28T00:00:00Z",
    })
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["checks_performed"] is False
    assert body["read_only"] is True


def test_http_route_rejects_unknown_status_values():
    app = FastAPI()
    from cin_monitoring_status_api import router
    app.include_router(router)
    response = TestClient(app).post("/monitoring/status", json={
        "provider_status": "probably-fine",
    })
    assert response.status_code == 422


@pytest.mark.parametrize("observed_at", [
    "2026-10-28T12:30:00",
    "not-a-timestamp",
])
def test_observed_at_rejects_invalid_or_timezone_naive_values(observed_at):
    with pytest.raises(ValidationError):
        MonitoringSnapshot(observed_at=observed_at)


def test_observed_at_accepts_timezone_aware_iso8601():
    snapshot = MonitoringSnapshot(observed_at="2026-10-28T12:30:00+05:30")
    assert snapshot.observed_at == "2026-10-28T12:30:00+05:30"


def test_snapshot_rejects_unrecognized_fields():
    with pytest.raises(ValidationError):
        MonitoringSnapshot(health="healthy", secret_internal_field="unexpected")


def test_snapshot_limits_warning_count():
    with pytest.raises(ValidationError):
        MonitoringSnapshot(warnings=[f"warning-{i}" for i in range(21)])


def test_degraded_health_is_reported_as_degraded():
    result = monitoring_status(MonitoringSnapshot(
        health="degraded", readiness="ready", provider_status="healthy",
        freshness="fresh",
    ))
    assert result["status"] == "degraded"

def test_warning_text_is_trimmed_before_returning():
    result = monitoring_status(MonitoringSnapshot(warnings=["  provider is slow  "]))
    assert result["warnings"] == ["provider is slow"]


@pytest.mark.parametrize("warning", ["", "   ", "x" * 501])
def test_warning_text_rejects_blank_or_overlong_entries(warning):
    with pytest.raises(ValidationError):
        MonitoringSnapshot(warnings=[warning])


def test_warning_text_accepts_exact_500_character_boundary():
    warning = "x" * 500
    snapshot = MonitoringSnapshot(warnings=[warning])
    assert snapshot.warnings == [warning]

@pytest.mark.parametrize("warning", [123, True, None, {"message": "slow"}])
def test_warning_text_rejects_non_string_entries(warning):
    with pytest.raises(ValidationError):
        MonitoringSnapshot(warnings=[warning])

from datetime import datetime, timezone, timedelta
from cin_monitoring_status_api import assess_timestamp_freshness


def test_timestamp_freshness_exact_age_boundary_is_fresh():
    now = datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc)
    result = assess_timestamp_freshness(
        "2026-10-28T11:55:00Z", now=now, max_age_seconds=300
    )
    assert result == {"freshness": "fresh", "age_seconds": 300, "reason": "within_limit"}


def test_timestamp_freshness_one_second_over_limit_is_stale():
    now = datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc)
    result = assess_timestamp_freshness(
        "2026-10-28T11:54:59Z", now=now, max_age_seconds=300
    )
    assert result["freshness"] == "stale"
    assert result["age_seconds"] == 301


def test_timestamp_freshness_fractional_second_over_limit_is_stale():
    now = datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc)
    result = assess_timestamp_freshness(
        "2026-10-28T11:54:59.500Z", now=now, max_age_seconds=300
    )
    assert result == {
        "freshness": "stale",
        "age_seconds": 301,
        "reason": "age_exceeds_limit",
    }


def test_timestamp_freshness_tolerates_small_future_clock_skew():
    now = datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc)
    result = assess_timestamp_freshness(
        "2026-10-28T12:04:00Z", now=now, max_age_seconds=300,
        future_tolerance_seconds=300,
    )
    assert result["freshness"] == "fresh"
    assert result["age_seconds"] == 0


def test_timestamp_freshness_rejects_future_timestamp_beyond_tolerance():
    now = datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc)
    result = assess_timestamp_freshness(
        "2026-10-28T12:05:01Z", now=now, max_age_seconds=300,
        future_tolerance_seconds=300,
    )
    assert result["freshness"] == "unknown"
    assert result["reason"] == "timestamp_too_far_in_future"


@pytest.mark.parametrize("timestamp", ["invalid", "2026-10-28T11:00:00"])
def test_timestamp_freshness_invalid_or_naive_timestamp_is_unknown(timestamp):
    now = datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc)
    result = assess_timestamp_freshness(timestamp, now=now, max_age_seconds=300)
    assert result["freshness"] == "unknown"


def test_timestamp_freshness_rejects_naive_clock_and_invalid_policy():
    result = assess_timestamp_freshness(
        "2026-10-28T11:59:00Z", now=datetime(2026, 10, 28, 12, 0),
        max_age_seconds=300,
    )
    assert result["freshness"] == "unknown"
    result = assess_timestamp_freshness(
        "2026-10-28T11:59:00Z", now=datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc),
        max_age_seconds=0,
    )
    assert result["freshness"] == "unknown"

def test_http_route_normalizes_warning_text_and_rejects_blank_warning():
    app = FastAPI()
    from cin_monitoring_status_api import router
    app.include_router(router)

    accepted = TestClient(app).post(
        "/monitoring/status", json={"warnings": ["  delayed feed  "]}
    )
    assert accepted.status_code == 200
    assert accepted.json()["warnings"] == ["delayed feed"]

    rejected = TestClient(app).post(
        "/monitoring/status", json={"warnings": ["   "]}
    )
    assert rejected.status_code == 422


from datetime import timedelta


def test_source_freshness_endpoint_validates_metadata_before_classifying_age():
    now = datetime.now(timezone.utc)
    observation = {
        "source_id": "coinbase_public",
        "subject": "BTC-USD",
        "observed_at": (now - timedelta(seconds=30)).isoformat(),
        "retrieved_at": (now - timedelta(seconds=10)).isoformat(),
        "timestamp_semantics": "snapshot_time",
        "provenance": "test-fixture",
    }
    app = FastAPI()
    from cin_monitoring_status_api import router
    app.include_router(router)
    response = TestClient(app).post("/monitoring/source-freshness", json={
        "observation": observation, "max_age_seconds": 300,
    })
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "fresh"
    assert body["metadata"]["validity"] == "valid_metadata"
    assert body["metadata"]["freshness_assessed"] is False
    assert body["freshness"]["freshness"] == "fresh"
    assert body["freshness_policy"] == {
        "max_age_seconds": 300,
        "selection": "caller_supplied_not_source_specific",
    }
    assert "not a CIN-enforced source-specific policy" in body["note"]
    assert body["checks_performed"] is False
    assert body["read_only"] is True


def test_source_freshness_endpoint_keeps_missing_identity_unknown():
    app = FastAPI()
    from cin_monitoring_status_api import router
    app.include_router(router)
    response = TestClient(app).post("/monitoring/source-freshness", json={
        "observation": {"subject": "BTC-USD"}, "max_age_seconds": 300,
    })
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "unknown"
    assert body["freshness"]["freshness"] == "unknown"
    assert body["checks_performed"] is False
