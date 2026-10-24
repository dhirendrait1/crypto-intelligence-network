"""Offline tests for CIN's public derivatives snapshot API."""
import asyncio
import json
import urllib.error

import pytest
from fastapi import FastAPI, HTTPException

import cin_derivatives_market_data_api as api


@pytest.mark.parametrize(
    "bids, asks",
    [
        ([["1e308", "1e308"]], [["1e308", "1"]]),
        ([["1e308", "1"]], [["1e308", "1"]]),
    ],
)
def test_snapshot_rejects_non_finite_order_book_arithmetic(monkeypatch, bids, asks):
    payloads = [
        {"symbol": "BTCUSDT", "openInterest": "1000", "time": 1_800_000_000_000},
        {"symbol": "BTCUSDT", "markPrice": "65000", "indexPrice": "65000", "lastFundingRate": "0.0001", "time": 1_800_000_000_000},
        [],
        {"bids": bids, "asks": asks},
    ]
    monkeypatch.setattr(api, "_get_json", lambda _path, _params: payloads.pop(0))
    with pytest.raises(ValueError, match="Order-book arithmetic"):
        api._snapshot("BTCUSDT")


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
        {"bids": [["65000", "2"], ["64990", "3"]], "asks": [["65010", "1"], ["65020", "4"]]},
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
    assert result["order_book"]["best_bid"] == 65000.0
    assert result["order_book"]["best_ask"] == 65010.0
    assert result["order_book"]["spread"] == 10.0
    assert result["order_book"]["spread_percent"] > 0
    assert result["order_book"]["bid_levels_used"] == 2
    assert result["order_book"]["ask_levels_used"] == 2
    assert result["order_book"]["retrieved_at"]
    assert result["order_book"]["bid_ask_notional_imbalance"] is not None
    assert len(calls) == 4
    assert all("order" not in params and "side" not in params for _, params in calls)



def test_order_book_retrieval_time_is_not_overwritten_by_snapshot_time(monkeypatch):
    from datetime import datetime, timezone

    times = [
        datetime(2026, 10, 24, 17, 0, 0, tzinfo=timezone.utc),
        datetime(2026, 10, 24, 17, 0, 5, tzinfo=timezone.utc),
    ]

    class ControlledDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return times.pop(0)

    payloads = [
        {"symbol": "BTCUSDT", "openInterest": "1000", "time": 1_800_000_000_000},
        {"symbol": "BTCUSDT", "markPrice": "65000", "indexPrice": "64990", "lastFundingRate": "0.0001", "time": 1_800_000_000_000},
        [
            {"symbol": "BTCUSDT", "sumOpenInterestValue": "1000000", "timestamp": 1_799_985_600_000},
            {"symbol": "BTCUSDT", "sumOpenInterestValue": "1020000", "timestamp": 1_800_000_000_000},
        ],
        {"bids": [["65000", "2"]], "asks": [["65010", "1"]]},
    ]
    monkeypatch.setattr(api, "datetime", ControlledDateTime)
    monkeypatch.setattr(api, "_get_json", lambda _path, _params: payloads.pop(0))

    result = api._snapshot("BTCUSDT")

    assert result["order_book"]["retrieved_at"] == "2026-10-24T17:00:00+00:00"
    assert result["retrieved_at"] == "2026-10-24T17:00:05+00:00"

def test_snapshot_rejects_wrong_symbol_or_invalid_payload(monkeypatch):
    monkeypatch.setattr(api, "_get_json", lambda _path, _params: {"symbol": "ETHUSDT"})
    with pytest.raises(ValueError, match="Unexpected open-interest"):
        api._snapshot("BTCUSDT")



@pytest.mark.parametrize(
    "history_row, message",
    [
        ({"symbol": "ETHUSDT", "sumOpenInterestValue": "1000000", "timestamp": 1_800_000_000_000}, "symbol did not match"),
        ({"symbol": "BTCUSDT", "sumOpenInterestValue": "-1", "timestamp": 1_800_000_000_000}, "invalid notional value"),
        ({"symbol": "BTCUSDT", "sumOpenInterestValue": "1000000", "timestamp": "invalid"}, "invalid timestamp"),
    ],
)
def test_snapshot_rejects_mislabelled_or_invalid_open_interest_history(monkeypatch, history_row, message):
    payloads = [
        {"symbol": "BTCUSDT", "openInterest": "1000", "time": 1_800_000_000_000},
        {"symbol": "BTCUSDT", "markPrice": "65000", "indexPrice": "64990", "lastFundingRate": "0.0001", "time": 1_800_000_000_000},
        [history_row],
        {"bids": [["65000", "2"]], "asks": [["65010", "1"]]},
    ]
    monkeypatch.setattr(api, "_get_json", lambda _path, _params: payloads.pop(0))
    with pytest.raises(ValueError, match=message):
        api._snapshot("BTCUSDT")

def test_snapshot_rejects_non_finite_derived_funding_percent(monkeypatch):
    payloads = [
        {"symbol": "BTCUSDT", "openInterest": "1000", "time": 1_800_000_000_000},
        {"symbol": "BTCUSDT", "markPrice": "65000", "indexPrice": "65000", "lastFundingRate": "1e308", "time": 1_800_000_000_000},
        [],
        {"bids": [["65000", "2"]], "asks": [["65010", "1"]]},
    ]
    monkeypatch.setattr(api, "_get_json", lambda _path, _params: payloads.pop(0))
    with pytest.raises(ValueError, match="Derived derivatives metrics"):
        api._snapshot("BTCUSDT")


@pytest.mark.parametrize(
    "field, value, message",
    [
        ("open_interest_time", "invalid", "open-interest provider payload contained an invalid timestamp"),
        ("premium_time", 10**400, "premium-index provider payload contained an invalid timestamp"),
        ("history_time", 10**400, "open-interest history contained an invalid timestamp"),
    ],
)
def test_snapshot_rejects_unrepresentable_provider_timestamps(monkeypatch, field, value, message):
    open_interest = {"symbol": "BTCUSDT", "openInterest": "1000", "time": 1_800_000_000_000}
    premium = {"symbol": "BTCUSDT", "markPrice": "65000", "indexPrice": "64990", "lastFundingRate": "0.0001", "time": 1_800_000_000_000}
    history = [{"symbol": "BTCUSDT", "sumOpenInterestValue": "1000000", "timestamp": 1_800_000_000_000}]
    if field == "open_interest_time":
        open_interest["time"] = value
    elif field == "premium_time":
        premium["time"] = value
    else:
        history[0]["timestamp"] = value
    payloads = [open_interest, premium, history, {"bids": [["65000", "2"]], "asks": [["65010", "1"]]}]
    monkeypatch.setattr(api, "_get_json", lambda _path, _params: payloads.pop(0))
    with pytest.raises(ValueError, match=message):
        api._snapshot("BTCUSDT")


def test_snapshot_rejects_crossed_order_book(monkeypatch):
    payloads = [
        {"symbol": "BTCUSDT", "openInterest": "1000", "time": 1_800_000_000_000},
        {"symbol": "BTCUSDT", "markPrice": "65000", "indexPrice": "65000", "lastFundingRate": "0.0001", "time": 1_800_000_000_000},
        [],
        {"bids": [["65010", "2"]], "asks": [["65000", "1"]]},
    ]
    monkeypatch.setattr(api, "_get_json", lambda _path, _params: payloads.pop(0))
    with pytest.raises(ValueError, match="best ask is below best bid"):
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

@pytest.mark.parametrize(("mark_price", "index_price"), [("0", "64990"), ("65000", "0"), ("65000", "-1"), ("65000", "invalid")])
def test_snapshot_rejects_invalid_mark_or_index_price(monkeypatch, mark_price, index_price):
    payloads = [
        {"symbol": "BTCUSDT", "openInterest": "1000", "time": 1_800_000_000_000},
        {"symbol": "BTCUSDT", "markPrice": mark_price, "indexPrice": index_price, "lastFundingRate": "0.0001", "time": 1_800_000_000_000},
        [],
        {"bids": [["65000", "2"]], "asks": [["65010", "1"]]},
    ]
    monkeypatch.setattr(api, "_get_json", lambda _path, _params: payloads.pop(0))
    with pytest.raises(ValueError, match="mark/index price"):
        api._snapshot("BTCUSDT")



def test_endpoint_classifies_provider_http_error(monkeypatch):
    def fail(_symbol):
        raise urllib.error.HTTPError("https://example.invalid", 429, "rate limited", {}, None)

    monkeypatch.setattr(api, "_snapshot", fail)
    with pytest.raises(HTTPException) as caught:
        asyncio.run(api.derivatives_market_snapshot(symbol="BTCUSDT"))
    assert caught.value.status_code == 503
    assert caught.value.detail["error"] == "http_error"
    assert caught.value.detail["http_status"] == 429


def test_snapshot_rejects_malformed_order_book_payload(monkeypatch):
    payloads = [
        {"symbol": "BTCUSDT", "openInterest": "1000", "time": 1_800_000_000_000},
        {"symbol": "BTCUSDT", "markPrice": "65000", "indexPrice": "65000", "lastFundingRate": "0.0001", "time": 1_800_000_000_000},
        [],
        {"bids": [], "asks": [["65010", "1"]]},
    ]
    monkeypatch.setattr(api, "_get_json", lambda _path, _params: payloads.pop(0))
    with pytest.raises(ValueError, match="no valid bid/ask levels"):
        api._snapshot("BTCUSDT")



@pytest.mark.parametrize(
    "failure",
    [
        RuntimeError("unexpected provider response"),
        UnicodeDecodeError("utf-8", b"\\xff", 0, 1, "invalid start byte"),
        TypeError("unexpected provider payload"),
        AttributeError("unexpected parser state"),
        Exception("unexpected generic provider failure"),
    ],
)
def test_endpoint_sanitizes_unexpected_provider_response_errors(monkeypatch, failure):
    def fail(_symbol):
        raise failure

    monkeypatch.setattr(api, "_snapshot", fail)
    with pytest.raises(HTTPException) as caught:
        asyncio.run(api.derivatives_market_snapshot(symbol="BTCUSDT"))

    assert caught.value.status_code == 502
    assert caught.value.detail["error"] == "invalid_response"
    assert caught.value.detail["message"] == "Derivatives provider response was invalid or incomplete."
    assert "unexpected provider response" not in str(caught.value.detail)


def test_derivatives_route_documents_strict_alphanumeric_symbol_contract():
    app = FastAPI()
    app.include_router(api.router)
    parameters = app.openapi()["paths"]["/derivatives/market-snapshot"]["get"]["parameters"]
    symbol = next(parameter for parameter in parameters if parameter["name"] == "symbol")
    assert symbol["schema"]["pattern"] == "^[A-Za-z0-9]+$"
    assert symbol["schema"]["minLength"] == 5
    assert symbol["schema"]["maxLength"] == 20



def test_derivatives_route_rejects_symbol_with_trailing_newline():
    with pytest.raises(HTTPException) as caught:
        asyncio.run(api.derivatives_market_snapshot(symbol="BTCUSDT\n"))
    assert caught.value.status_code == 400
    assert caught.value.detail["error"] == "invalid_symbol"
