from datetime import datetime, timezone

import pytest

from cin_source_observation_contract import validate_source_observation


NOW = datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc)


def base_observation(**overrides):
    value = {
        "source_id": "coinbase_public",
        "subject": "BTC-USD",
        "observed_at": "2026-10-28T11:59:00Z",
        "retrieved_at": "2026-10-28T11:59:05Z",
        "timestamp_semantics": "candle_close_time",
        "provenance": "public-candles-endpoint",
        "quote_currency": "USD",
        "interval": "1m",
    }
    value.update(overrides)
    return value


def test_fractional_observation_age_is_rounded_up_not_truncated():
    result = validate_source_observation(
        base_observation(
            observed_at="2026-10-28T11:54:59.500Z",
            retrieved_at="2026-10-28T12:00:00Z",
        ),
        now=NOW,
    )
    assert result["validity"] == "valid_metadata"
    assert result["age_seconds_at_retrieval"] == 301
    assert result["freshness_assessed"] is False


def test_valid_envelope_preserves_provenance_and_does_not_claim_freshness():
    result = validate_source_observation(base_observation(), now=NOW)
    assert result["validity"] == "valid_metadata"
    assert result["source_id"] == "coinbase_public"
    assert result["quote_currency"] == "USD"
    assert result["age_seconds_at_retrieval"] == 5
    assert result["freshness_assessed"] is False
    assert result["source_authenticity_verified"] is False


@pytest.mark.parametrize("field", [
    "source_id", "subject", "observed_at", "retrieved_at",
    "timestamp_semantics", "provenance",
])
def test_missing_required_metadata_is_unknown(field):
    observation = base_observation()
    observation.pop(field)
    assert validate_source_observation(observation, now=NOW)["validity"] == "unknown"


@pytest.mark.parametrize("timestamp", [
    "not-a-time", "2026-10-28T11:59:00",
])
def test_invalid_or_naive_observation_timestamp_is_unknown(timestamp):
    result = validate_source_observation(
        base_observation(observed_at=timestamp), now=NOW
    )
    assert result["reason"] == "invalid_or_timezone_naive_timestamp"


def test_unknown_timestamp_semantics_is_unknown():
    result = validate_source_observation(
        base_observation(timestamp_semantics="some-time"), now=NOW
    )
    assert result["reason"] == "unknown_timestamp_semantics"


def test_observation_newer_than_retrieval_is_unknown():
    result = validate_source_observation(
        base_observation(observed_at="2026-10-28T11:59:06Z"), now=NOW
    )
    assert result["reason"] == "observation_after_retrieval"


def test_future_retrieval_is_unknown():
    result = validate_source_observation(
        base_observation(retrieved_at="2026-10-28T12:01:00Z"), now=NOW
    )
    assert result["reason"] == "retrieval_timestamp_in_future"


@pytest.mark.parametrize("field", ["quote_currency", "interval"])
def test_candles_require_quote_currency_and_interval(field):
    observation = base_observation()
    observation.pop(field)
    result = validate_source_observation(observation, now=NOW)
    assert result["validity"] == "unknown"


def test_non_candle_observation_does_not_require_quote_currency():
    observation = base_observation(
        timestamp_semantics="publication_time",
        quote_currency=None,
        interval=None,
    )
    result = validate_source_observation(observation, now=NOW)
    assert result["validity"] == "valid_metadata"


def test_naive_evaluation_clock_is_unknown():
    result = validate_source_observation(
        base_observation(), now=datetime(2026, 10, 28, 12, 0)
    )
    assert result["reason"] == "timezone_required_for_clock"


def test_non_mapping_observation_is_unknown():
    result = validate_source_observation([], now=NOW)
    assert result["reason"] == "observation_must_be_mapping"
