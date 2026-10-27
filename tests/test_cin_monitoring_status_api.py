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
