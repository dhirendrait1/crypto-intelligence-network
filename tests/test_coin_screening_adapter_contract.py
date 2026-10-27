"""Offline regression tests for CIN screening provider normalization.

These tests deliberately mock provider HTTP responses; they do not claim live API
availability. Run with: pytest -q tests/test_coin_screening_adapter_contract.py
"""
import json
import math
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

import coin_screening_step2 as screening


def _response(payload, status=200):
    response = MagicMock()
    response.status = status
    response.read.return_value = json.dumps(payload).encode("utf-8")
    response.__enter__.return_value = response
    response.__exit__.return_value = False
    return response


def _paprika_row(**overrides):
    row = {
        "id": "btc-bitcoin",
        "symbol": "BTC",
        "name": "Bitcoin",
        "circulating_supply": 10,
        "total_supply": 12,
        "max_supply": 20,
        "last_updated": "2026-10-27T10:00:00Z",
        "quotes": {
            "USD": {
                "price": 100,
                "market_cap": 1000,
                "volume_24h": 50,
                "percent_change_24h": 2,
            }
        },
    }
    row.update(overrides)
    return row


def _force_primary_failure():
    return urllib.error.HTTPError("https://api.coingecko.com", 429, "rate limited", {}, None)


def test_coinpaprika_fallback_keeps_requested_quote_currency():
    with patch.object(screening.urllib.request, "urlopen", side_effect=[
        _force_primary_failure(), _response([_paprika_row()])
    ]):
        rows = screening._request_markets("usd", 10)

    assert rows[0]["_cin_provider"] == "CoinPaprika"
    assert rows[0]["_cin_quote_currency"] == "USD"
    assert rows[0]["current_price"] == 100


def test_coinpaprika_does_not_substitute_usd_for_usdt():
    with patch.object(screening.urllib.request, "urlopen", side_effect=[
        _force_primary_failure(), _response([_paprika_row()])
    ]):
        with pytest.raises(screening.MarketDataProviderFailure):
            screening._request_markets("usdt", 10)


@pytest.mark.parametrize("value", [True, "123", float("nan"), float("inf"), -1])
def test_coinpaprika_invalid_price_is_missing_evidence(value):
    row = _paprika_row()
    row["quotes"]["USD"]["price"] = value
    with patch.object(screening.urllib.request, "urlopen", side_effect=[
        _force_primary_failure(), _response([row])
    ]):
        rows = screening._request_markets("usd", 10)

    assert rows[0]["current_price"] is None
    assert rows[0]["fully_diluted_valuation"] is None


def test_fdv_requires_positive_known_max_supply():
    row = _paprika_row()
    row["max_supply"] = None
    with patch.object(screening.urllib.request, "urlopen", side_effect=[
        _force_primary_failure(), _response([row])
    ]):
        rows = screening._request_markets("usd", 10)
    assert rows[0]["fully_diluted_valuation"] is None


def test_canonical_market_rows_drops_missing_and_duplicate_ids_deterministically():
    rows, counts = screening._canonical_market_rows([
        {"id": "bitcoin", "symbol": "BTC"},
        {"id": "BITCOIN", "symbol": "BTC-duplicate"},
        {"symbol": "NO-ID"},
        {"id": "ethereum", "symbol": "ETH"},
    ])
    assert [row["id"] for row in rows] == ["bitcoin", "ethereum"]
    assert counts == {
        "input_row_count": 4,
        "invalid_identity_count": 1,
        "duplicate_id_count": 1,
        "unique_identity_count": 2,
    }


@pytest.mark.parametrize(
    "timestamp,expected",
    [
        ("not-a-time", "unknown"),
        ("2026-10-27T10:00:00", "unknown"),
        ("2026-10-27T10:00:00Z", "stale"),
        (None, "unknown"),
    ],
)
def test_market_freshness_requires_timezone_aware_timestamp(timestamp, expected):
    state, age = screening._market_freshness(timestamp)
    assert state == expected
    if expected == "unknown":
        assert age is None
    else:
        assert age is not None and age >= 0


def test_provider_failure_is_sanitized_and_reports_both_provider_classes():
    with patch.object(screening.urllib.request, "urlopen", side_effect=[
        _force_primary_failure(),
        urllib.error.URLError("secret endpoint detail"),
    ]):
        with pytest.raises(screening.MarketDataProviderFailure) as exc:
            screening._request_markets("usd", 10)

    assert exc.value.primary_kind == "http_error"
    assert exc.value.primary_status == 429
    assert exc.value.fallback_kind == "network_error"
    assert "secret endpoint detail" not in str(exc.value)
