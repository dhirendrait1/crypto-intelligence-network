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


def test_request_rejects_excessive_evidence_batch():
    with pytest.raises(ValidationError):
        GrowthFundamentalsRequest(
            symbol="ETH",
            evidence=[{"category": "usage_and_adoption"}] * 201,
        )


def test_request_accepts_normalized_symbol_alphabet():
    request = GrowthFundamentalsRequest(symbol="eth.v2-test_1")
    assert request.symbol == "eth.v2-test_1"
