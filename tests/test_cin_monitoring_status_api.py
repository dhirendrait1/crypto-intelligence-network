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
