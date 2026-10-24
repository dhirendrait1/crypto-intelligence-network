"""Offline tests for CIN's public derivatives snapshot API."""
import asyncio
import json
import urllib.error

import pytest
from fastapi import HTTPException

import cin_derivatives_market_data_api as api


def test_snapshot_preserves_source_times_and_never_invents_liquidations(monkeypatch):
    payloads = [
        {"symbol": "BTCUSDT", "openInterest": "1000.0", "time": 1_800_000_000_000},
        {
            "symbol": "BTCUSDT", "markPrice": "65000.5", "indexPrice": "64990.0",
            "lastFundingRate": "0.0001", "nextFundingTime": 1_800_028_800_000,
            "time": 1_800_000_000_500,
        },
        [
            {"symbol": "BTCUSDT", "sumOpenInterestValue": "1000000", "timestamp": 1_799_985_600_000},
            {"symbol": "BTCUSDT", "sumOpenInterestValue": "1020000", "timestamp": 1_800_000_000_000},
        ],
    ]
    calls = []

    def fake_get_json(path, params):
        calls.append((path, params))
        return payloads.pop(0)

    monkeypatch.setattr(api, "_get_json", fake_get_json)
    result = api._snapshot("BTCUSDT")

    assert result["mode"] == "read_only"
    assert result["source"] == "Binance USDⓈ-M Futures public market-data API"
    assert result["data"]["open_interest_contracts"] == 1000.0
    assert result["data"]["open_interest_value_change_4h_percent"] == 2.0
    assert result["data"]["funding_rate_percent_per_interval"] == 0.01
    assert result["provider_timestamps"]["open_interest"] is not None
    assert result["retrieved_at"]
    assert result["liquidations"]["status"] == "not_available"
    assert len(calls) == 3
    assert all("order" not in params and "side" not in params for _, params in calls)


def test_snapshot_rejects_wrong_symbol_or_invalid_payload(monkeypatch):
    monkeypatch.setattr(api, "_get_json", lambda _path, _params: {"symbol": "ETHUSDT"})
    with pytest.raises(ValueError, match="Unexpected open-interest"):
        api._snapshot("BTCUSDT")


def test_endpoint_classifies_network_failure_without_claiming_live_data(monkeypatch):
    def fail(_symbol):
        raise urllib.error.URLError("offline")

    monkeypatch.setattr(api, "_snapshot", fail)
    with pytest.raises(HTTPException) as caught:
        asyncio.run(api.derivatives_market_snapshot(symbol="BTCUSDT"))
    assert caught.value.status_code == 503
    assert caught.value.detail["error"] == "network_error"


def test_finite_number_rejects_nan_and_infinity():
    assert api._finite_number("NaN") is None
    assert api._finite_number("Infinity") is None
    assert api._finite_number("12.5") == 12.5
