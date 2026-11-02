"""Offline tests for CIN forecast ledger and post-horizon outcome scoring."""
from datetime import datetime, timedelta, timezone

import pytest

from cin_forecast_ledger import (
    evaluate_forecast_outcome,
    forecast_calibration_summary,
    record_forecast,
)


NOW = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)


def _record(path, **overrides):
    values = {
        "forecast_id": "forecast-btc-001",
        "asset": "BTC",
        "source": "coinbase-public",
        "issued_at": NOW,
        "horizon_seconds": 3600,
        "reference_price": 65000,
        "target_price": 67000,
        "direction": "up",
        "invalidation_conditions": {"max_age_seconds": 300, "note": "documented but not auto-evaluated"},
    }
    values.update(overrides)
    return record_forecast(path, **values)


def test_forecast_records_explicit_horizon_and_provenance(tmp_path):
    result = _record(tmp_path / "forecasts.sqlite3")
    assert result["asset"] == "BTC"
    assert result["source"] == "coinbase-public"
    assert result["target_at"] == (NOW + timedelta(hours=1)).isoformat()
    assert result["status"] == "pending_outcome"


@pytest.mark.parametrize("overrides", [
    {"horizon_seconds": True},
    {"horizon_seconds": 59},
    {"direction": "flat"},
    {"target_price": 64000},
    {"reference_price": float("nan")},
    {"invalidation_conditions": {"x": float("nan")}},
])
def test_invalid_forecast_contracts_rejected(tmp_path, overrides):
    with pytest.raises(ValueError):
        _record(tmp_path / "forecasts.sqlite3", **overrides)


def test_forecast_id_is_immutable_and_duplicate_rejected(tmp_path):
    path = tmp_path / "forecasts.sqlite3"
    _record(path)
    with pytest.raises(Exception):
        _record(path, target_price=68000)


def test_outcome_cannot_use_pre_horizon_observation(tmp_path):
    path = tmp_path / "forecasts.sqlite3"
    _record(path)
    with pytest.raises(ValueError, match="at or after forecast target_at"):
        evaluate_forecast_outcome(
            path, forecast_id="forecast-btc-001", observation_source="coinbase",
            observation_at=NOW + timedelta(minutes=59), observed_price=67000,
            evaluated_at=NOW + timedelta(hours=1),
        )


def test_outcome_rejects_observation_after_evaluation_time(tmp_path):
    path = tmp_path / "forecasts.sqlite3"
    _record(path)
    with pytest.raises(ValueError, match="observation_at cannot be in the future relative to evaluated_at"):
        evaluate_forecast_outcome(
            path, forecast_id="forecast-btc-001", observation_source="coinbase",
            observation_at=NOW + timedelta(hours=1), observed_price=67000,
            evaluated_at=NOW + timedelta(minutes=59),
        )


def test_outcome_records_timestamped_source_and_error_metrics(tmp_path):
    path = tmp_path / "forecasts.sqlite3"
    _record(path)
    result = evaluate_forecast_outcome(
        path, forecast_id="forecast-btc-001", observation_source="kraken-public",
        observation_at=NOW + timedelta(hours=1, minutes=1), observed_price=67500,
        evaluated_at=NOW + timedelta(hours=1, minutes=2),
    )
    assert result["direction_correct"] is True
    assert result["absolute_error"] == 500
    assert result["percentage_error"] == pytest.approx(500 / 67000 * 100)
    assert result["observation_source"] == "kraken-public"


def test_outcome_is_immutable_and_summary_is_descriptive(tmp_path):
    path = tmp_path / "forecasts.sqlite3"
    _record(path)
    kwargs = dict(
        forecast_id="forecast-btc-001", observation_source="coinbase-public",
        observation_at=NOW + timedelta(hours=1), observed_price=66000,
        evaluated_at=NOW + timedelta(hours=1),
    )
    evaluate_forecast_outcome(path, **kwargs)
    with pytest.raises(Exception):
        evaluate_forecast_outcome(path, **kwargs)
    summary = forecast_calibration_summary(path)
    assert summary["forecast_count"] == 1
    assert summary["evaluated_count"] == 1
    assert summary["pending_outcome_count"] == 0
    assert summary["directional_accuracy"] == 0.0
    assert summary["status"] == "descriptive_only"


def test_summary_empty_is_not_zero_accuracy(tmp_path):
    summary = forecast_calibration_summary(tmp_path / "empty.sqlite3")
    assert summary["directional_accuracy"] is None
    assert summary["mean_absolute_price_error"] is None
    assert summary["status"] == "no_evaluated_forecasts"


def test_forecast_requires_timezone_aware_issue_time(tmp_path):
    with pytest.raises(ValueError, match="explicit timezone"):
        _record(tmp_path / "forecasts.sqlite3", issued_at="2026-10-27T12:00:00")
