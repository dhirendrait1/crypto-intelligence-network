"""Offline tests for the CIN growth fundamentals request boundary."""
import pytest
from pydantic import ValidationError

from growth_fundamentals_api import GrowthFundamentalsRequest


@pytest.mark.parametrize("symbol", [" ETH", "ETH ", "ETH/USDT", ""])
def test_request_rejects_invalid_symbol_format(symbol):
    with pytest.raises(ValidationError):
        GrowthFundamentalsRequest(symbol=symbol)


def test_request_accepts_zero_day_freshness_threshold():
    request = GrowthFundamentalsRequest(symbol="ETH", max_age_days=0)
    assert request.max_age_days == 0


def test_request_rejects_boolean_freshness_threshold():
    with pytest.raises(ValidationError):
        GrowthFundamentalsRequest(symbol="ETH", max_age_days=True)


@pytest.mark.parametrize("threshold", [30.0, "30", -1, 3651])
def test_request_rejects_non_integer_or_out_of_range_freshness_threshold(threshold):
    with pytest.raises(ValidationError):
        GrowthFundamentalsRequest(symbol="ETH", max_age_days=threshold)


def test_request_rejects_excessive_evidence_batch():
    with pytest.raises(ValidationError):
        GrowthFundamentalsRequest(
            symbol="ETH",
            evidence=[{"category": "usage_and_adoption"}] * 201,
        )


def test_request_accepts_normalized_symbol_alphabet():
    request = GrowthFundamentalsRequest(symbol="eth.v2-test_1")
    assert request.symbol == "eth.v2-test_1"


def test_request_rejects_oversized_evidence_metadata_fields():
    valid = {
        "category": "usage_and_adoption",
        "source_name": "Example",
        "source_url": "https://example.com/report",
        "published_at": "2026-10-01T00:00:00Z",
        "status": "unverified",
        "notes": "ok",
    }
    limits = {
        "source_name": "s" * 201,
        "source_url": "https://" + "a" * 2042,
        "published_at": "t" * 65,
        "status": "s" * 33,
        "notes": "n" * 2001,
    }
    for field, oversized in limits.items():
        with pytest.raises(ValidationError):
            GrowthFundamentalsRequest(symbol="ETH", evidence=[{**valid, field: oversized}])


def test_request_rejects_unknown_top_level_fields():
    with pytest.raises(ValidationError):
        GrowthFundamentalsRequest(symbol="ETH", max_age_day=30)


def test_request_rejects_unknown_evidence_record_fields():
    with pytest.raises(ValidationError):
        GrowthFundamentalsRequest(
            symbol="ETH",
            evidence=[{"category": "usage_and_adoption", "published": "2026-10-01"}],
        )

def test_request_accepts_maximum_documented_freshness_threshold():
    request = GrowthFundamentalsRequest(symbol="ETH", max_age_days=3650)
    assert request.max_age_days == 3650


def test_request_accepts_maximum_documented_evidence_batch():
    record = {
        "category": "usage_and_adoption",
        "source_name": "Example",
        "source_url": "https://example.com/report",
        "published_at": "2026-10-01T00:00:00Z",
        "status": "unverified",
    }
    request = GrowthFundamentalsRequest(symbol="ETH", evidence=[record] * 200)
    assert len(request.evidence) == 200


def test_request_rejects_symbol_with_trailing_newline():
    with pytest.raises(ValidationError):
        GrowthFundamentalsRequest(symbol="ETH\n")

