"""Regression tests for read-only public market candle provenance and closure."""
import asyncio
from datetime import datetime, timezone

import pytest

import cin_public_market_candles_api as api


def _row(open_time_ms: int, close_time_ms: int, close: float = 100.0):
    return {
        "open_time": open_time_ms,
        "open": close - 1,
        "high": close + 2,
        "low": close - 2,
        "close": close,
        "volume": 12.5,
        "close_time": close_time_ms,
        "_source": "Kraken public OHLC API (fallback after Binance HTTP 451)",
        "_source_endpoint": api.KRAKEN_OHLC_URL,
        "_provider_pair_key": "XXBTZUSD",
        "_provider_quote_currency": "USD",
    }



def test_clean_candles_rejects_invalid_rows_and_orders_unique_timestamps():
    valid_later = _row(2_000, 2_999)
    valid_earlier = _row(1_000, 1_999)
    invalid_price = _row(3_000, 3_999)
    invalid_price["close"] = float("nan")
    invalid_volume = _row(4_000, 4_999)
    invalid_volume["volume"] = -1
    # Exact duplicates are safe to collapse; conflicting rows are rejected separately. 
    duplicate = _row(1_000, 1_999, close=100.0)

    cleaned = api._clean_candles(
        [valid_later, invalid_price, valid_earlier, invalid_volume, duplicate],
        "Test provider",
    )

    assert [row["open_time"] for row in cleaned] == [1_000, 2_000]
    assert cleaned[0]["close"] == 100.0


def test_clean_candles_fails_when_provider_returns_only_invalid_rows():
    invalid = _row(1_000, 999)
    with pytest.raises(ValueError, match="returned no valid candles"):
        api._clean_candles([invalid], "Test provider")

def test_kraken_fallback_reports_actual_pair_key_and_quote(monkeypatch):
    now_seconds = int(datetime.now(timezone.utc).timestamp()) - 600
    payload = {
        "error": [],
        "result": {
            "XXBTZUSD": [
                [now_seconds, "100", "102", "98", "101", "100", "4", 10],
            ],
            "last": 123,
        },
    }
    monkeypatch.setattr(api, "_request_json", lambda _url: payload)

    rows = api._fetch_kraken("BTCUSD", "1h", 5)

    assert rows[0]["_provider_pair_key"] == "XXBTZUSD"
    assert rows[0]["_provider_quote_currency"] == "USD"


def test_kraken_fallback_preserves_provider_documented_forming_candle(monkeypatch):
    # Kraken documents that the final OHLC row is always the current,
    # not-yet-committed timeframe. Keep it available for status labeling;
    # downstream technical analysis separately excludes unclosed candles.
    now_seconds = int(datetime.now(timezone.utc).timestamp())
    current_hour_open = now_seconds - (now_seconds % 3600)
    previous_hour_open = current_hour_open - 3600
    payload = {
        "error": [],
        "result": {
            "XXBTZUSD": [
                [previous_hour_open, "100", "102", "98", "101", "100", "4", 10],
                [current_hour_open, "101", "103", "100", "102", "101", "2", 4],
            ],
            "last": current_hour_open,
        },
    }
    monkeypatch.setattr(api, "_request_json", lambda _url: payload)

    rows = api._fetch_kraken("BTCUSD", "1h", 5)

    assert [row["open_time"] for row in rows] == [
        previous_hour_open * 1000, current_hour_open * 1000
    ]
    assert rows[-1]["close_time"] == (current_hour_open + 3600) * 1000 - 1


@pytest.mark.parametrize("returned_pair", ["ETHUSD", "XXBTUSDT"])
def test_kraken_fallback_rejects_returned_pair_or_quote_mismatch(returned_pair, monkeypatch):
    now_seconds = int(datetime.now(timezone.utc).timestamp()) - 7200
    payload = {
        "error": [],
        "result": {
            returned_pair: [
                [now_seconds, "100", "102", "98", "101", "100", "4", 10],
            ],
            "last": now_seconds,
        },
    }
    monkeypatch.setattr(api, "_request_json", lambda _url: payload)

    with pytest.raises(ValueError, match="different trading pair"):
        api._fetch_kraken("BTCUSD", "1h", 5)


def test_kraken_fallback_rejects_unsupported_interval_without_network(monkeypatch):
    def unexpected_request(_url):
        raise AssertionError("unsupported interval must be rejected before network access")

    monkeypatch.setattr(api, "_request_json", unexpected_request)
    with pytest.raises(ValueError, match="does not support interval 2h"):
        api._fetch_kraken("BTCUSDT", "2h", 10)


def test_candle_routes_document_strict_symbol_format():
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(api.router)
    schema = app.openapi()

    for path in ("/market-candles", "/technical-analysis/market"):
        parameters = schema["paths"][path]["get"]["parameters"]
        symbol = next(parameter for parameter in parameters if parameter["name"] == "symbol")
        assert symbol["schema"]["pattern"] == "^[A-Za-z0-9]+$"
        assert symbol["schema"]["minLength"] == 5
        assert symbol["schema"]["maxLength"] == 20


def test_market_candles_reports_pair_and_closed_status(monkeypatch):
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    rows = [
        _row(now_ms - 3_600_000 * 3, now_ms - 3_600_000 * 2),
        _row(now_ms - 3_600_000 * 2, now_ms - 3_600_000),
        _row(now_ms - 3_600_000, now_ms - 1),
        _row(now_ms, now_ms + 3_599_999),
    ]
    monkeypatch.setattr(api, "_load", lambda *_args: asyncio.sleep(0, result=rows))

    response = asyncio.run(api.get_market_candles("BTCUSDT", "1h", 10))

    assert response["mode"] == "read_only"
    assert response["provider_pair_key"] == "XXBTZUSD"
    assert response["provider_quote_currency"] == "USD"
    assert [c["candle_status"] for c in response["data"]] == [
        "closed", "closed", "closed", "forming"
    ]
    assert [c["is_closed"] for c in response["data"]] == [True, True, True, False]


def test_freshness_metadata_warns_when_latest_closed_candle_is_old():
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    old = _row(now_ms - 5 * 3_600_000, now_ms - 4 * 3_600_000)

    result = api._freshness_metadata([old], "1h", now_ms)

    assert result["latest_closed_candle_age_seconds"] >= 4 * 3_600_000 / 1000
    assert result["stale_threshold_seconds"] == 7200
    assert "older than the 1h freshness threshold" in result["stale_data_warning"]


def test_freshness_metadata_does_not_warn_for_recent_closed_candle():
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    recent = _row(now_ms - 3_600_000, now_ms - 1000)

    result = api._freshness_metadata([recent], "1h", now_ms)

    assert result["latest_closed_candle_age_seconds"] < 2
    assert result["stale_data_warning"] is None


def test_freshness_metadata_explicitly_handles_no_closed_candles():
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    forming = _row(now_ms, now_ms + 3_599_999)

    result = api._freshness_metadata([forming], "1h", now_ms)

    assert result["latest_closed_candle_age_seconds"] is None
    assert "No completed candle" in result["stale_data_warning"]

def test_market_analysis_excludes_forming_candle_by_default(monkeypatch):
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    rows = [
        _row(now_ms - (7 - i) * 3_600_000, now_ms - (6 - i) * 3_600_000, 100 + i)
        for i in range(6)
    ]
    rows.append(_row(now_ms, now_ms + 3_599_999, 999.0))
    seen = {}

    async def fake_load(*_args):
        return rows

    def fake_analyze(candles):
        seen["candles"] = candles
        return {"input": {}, "limitations": []}

    monkeypatch.setattr(api, "_load", fake_load)
    monkeypatch.setattr(api, "analyze_ohlc", fake_analyze)

    response = asyncio.run(api.analyze_public_market("BTCUSDT", "1h", 10))

    assert response["input"]["closed_candles_only"] is True
    assert response["input"]["candles_requested"] == 7
    assert response["input"]["candles_used"] == 6
    assert response["input"]["forming_candles_excluded"] == 1
    assert any("excludes forming candles from analysis" in item for item in response["limitations"])
    assert not any("includes the latest candle even when it is still forming" in item for item in response["limitations"])
    assert len(seen["candles"]) == 6
    assert all(c["close"] != 999.0 for c in seen["candles"])
    assert all(c["volume"] == 12.5 for c in seen["candles"])
    assert response["input"]["volume_included_in_source"] is True
    assert response["input"]["freshness"]["latest_closed_candle_age_seconds"] is not None
    assert response["input"]["freshness"]["stale_data_warning"] is None


def test_market_analysis_sanitizes_unexpected_analysis_failure(monkeypatch):
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    rows = [
        _row(now_ms - (7 - i) * 3_600_000, now_ms - (6 - i) * 3_600_000, 100 + i)
        for i in range(6)
    ]

    async def fake_load(*_args):
        return rows

    def fail_analysis(_candles):
        raise RuntimeError("private parser detail")

    monkeypatch.setattr(api, "_load", fake_load)
    monkeypatch.setattr(api, "analyze_ohlc", fail_analysis)

    with pytest.raises(api.HTTPException) as exc:
        asyncio.run(api.analyze_public_market("BTCUSDT", "1h", 10))

    assert exc.value.status_code == 502
    assert exc.value.detail == "Technical analysis failed on the fetched candle data."
    assert "private parser detail" not in str(exc.value.detail)


def test_market_analysis_rejects_fewer_than_five_closed_candles(monkeypatch):
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    rows = [
        _row(now_ms - 3_600_000 * 2, now_ms - 3_600_000),
        _row(now_ms - 3_600_000, now_ms - 1),
        _row(now_ms, now_ms + 3_599_999),
        _row(now_ms + 3_600_000, now_ms + 7_199_999),
        _row(now_ms + 7_200_000, now_ms + 10_799_999),
    ]

    async def fake_load(*_args):
        return rows

    monkeypatch.setattr(api, "_load", fake_load)

    with pytest.raises(api.HTTPException) as exc:
        asyncio.run(api.analyze_public_market("BTCUSDT", "1h", 10))

    assert exc.value.status_code == 422
    assert "completed candles" in exc.value.detail


@pytest.mark.parametrize("interval, kraken_minutes", sorted(api.KRAKEN_INTERVALS.items()))
def test_each_declared_kraken_fallback_interval_is_mapped(interval, kraken_minutes, monkeypatch):
    import urllib.parse

    captured = {}

    def fake_request(url):
        captured.update(urllib.parse.parse_qs(urllib.parse.urlparse(url).query))
        now_seconds = int(datetime.now(timezone.utc).timestamp()) - 7200
        return {
            "error": [],
            "result": {
                "XXBTZUSD": [
                    [now_seconds, "100", "102", "98", "101", "100", "4", 10],
                ],
                "last": 123,
            },
        }

    monkeypatch.setattr(api, "_request_json", fake_request)
    rows = api._fetch_kraken("BTCUSD", interval, 5)

    assert rows
    assert captured["interval"] == [str(kraken_minutes)]



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
def test_market_provider_shape_failures_return_sanitized_502(monkeypatch, failure):
    def fail(*_args):
        raise failure

    monkeypatch.setattr(api, "_fetch_binance", fail)

    with pytest.raises(api.HTTPException) as caught:
        asyncio.run(api._load("BTCUSDT", "1h", 10))

    assert caught.value.status_code == 502
    assert caught.value.detail == "Public market-data provider returned an invalid response."
    assert "unexpected provider response" not in str(caught.value.detail)


def test_kraken_fallback_unexpected_response_returns_controlled_503(monkeypatch):
    def binance_451(*_args):
        raise api.urllib.error.HTTPError(
            api.BINANCE_KLINES_URL, 451, "unavailable for legal reasons", {}, None
        )

    def fail_fallback(*_args):
        raise RuntimeError("unexpected fallback response")

    monkeypatch.setattr(api, "_fetch_binance", binance_451)
    monkeypatch.setattr(api, "_fetch_kraken", fail_fallback)

    with pytest.raises(api.HTTPException) as caught:
        asyncio.run(api._load("BTCUSD", "1h", 10))

    assert caught.value.status_code == 503
    assert "Kraken fallback unavailable" in caught.value.detail
    assert "unexpected fallback response" not in str(caught.value.detail)

@pytest.mark.parametrize(
    "symbol, expected_pair_key, expected_quote",
    [
        ("BTCUSD", "XXBTZUSD", "USD"),
        ("ETHUSDT", "ETHUSDT", "USDT"),
    ],
)
def test_kraken_fallback_maps_requested_symbol_and_reports_actual_pair(
    symbol, expected_pair_key, expected_quote, monkeypatch
):
    import urllib.parse

    captured = {}

    def fake_request(url):
        captured.update(urllib.parse.parse_qs(urllib.parse.urlparse(url).query))
        return {
            "error": [],
            "result": {
                expected_pair_key: [
                    [int(datetime.now(timezone.utc).timestamp()) - 7200,
                     "100", "102", "98", "101", "100", "4", 10],
                ],
                "last": 123,
            },
        }

    monkeypatch.setattr(api, "_request_json", fake_request)
    rows = api._fetch_kraken(symbol, "1h", 5)

    assert captured["pair"] == [symbol if symbol.startswith("ETH") else "XBTUSD"]
    assert rows[0]["_provider_pair_key"] == expected_pair_key
    assert rows[0]["_provider_quote_currency"] == expected_quote



@pytest.mark.parametrize("timestamp", [10**100, -(10**100)])
def test_clean_candles_rejects_unrepresentable_timestamps(timestamp):
    row = _row(timestamp, timestamp + 1)
    with pytest.raises(ValueError, match="returned no valid candles"):
        api._clean_candles([row], "Test provider")

def test_clean_candles_rejects_os_error_from_timestamp_conversion(monkeypatch):
    class TimestampConversionFailure:
        @staticmethod
        def fromtimestamp(*_args, **_kwargs):
            raise OSError("timestamp is outside platform range")

    monkeypatch.setattr(api, "datetime", TimestampConversionFailure)
    row = _row(1_000, 1_999)
    with pytest.raises(ValueError, match="returned no valid candles"):
        api._clean_candles([row], "Test provider")

@pytest.mark.parametrize(
    "month_start, expected_days",
    [
        ("2024-01-01T00:00:00+00:00", 31),
        ("2024-02-01T00:00:00+00:00", 29),
        ("2023-02-01T00:00:00+00:00", 28),
        ("2024-04-01T00:00:00+00:00", 30),
        ("2024-12-01T00:00:00+00:00", 31),
    ],
)
def test_monthly_interval_duration_uses_calendar_month_boundaries(month_start, expected_days):
    start_ms = int(datetime.fromisoformat(month_start).timestamp() * 1000)
    assert api._interval_duration_ms("1M", start_ms) == expected_days * 86_400_000


def test_monthly_freshness_threshold_uses_latest_candle_calendar_month():
    start = datetime(2024, 2, 1, tzinfo=timezone.utc)
    open_ms = int(start.timestamp() * 1000)
    close_ms = int(datetime(2024, 2, 29, 23, 59, 59, 999000, tzinfo=timezone.utc).timestamp() * 1000)
    row = _row(open_ms, close_ms)
    result = api._freshness_metadata([row], "1M", close_ms + 1000)
    assert result["stale_threshold_seconds"] == 2 * 29 * 86_400

def test_candle_time_consistency_rejects_fixed_interval_close_mismatch():
    row = _row(1_700_000_000_000, 1_700_003_599_998)
    assert not api._candle_time_consistent(row, "1h")


def test_candle_time_consistency_accepts_fixed_interval_duration_without_epoch_anchor_assumption():
    opened = 1_700_000_000_000
    row = _row(opened, opened + 3_600_000 - 1)
    assert api._candle_time_consistent(row, "1h")


@pytest.mark.parametrize("month_start, month_end", [
    ("2024-02-01T00:00:00+00:00", "2024-02-29T23:59:59.999000+00:00"),
    ("2023-02-01T00:00:00+00:00", "2023-02-28T23:59:59.999000+00:00"),
    ("2024-04-01T00:00:00+00:00", "2024-04-30T23:59:59.999000+00:00"),
])
def test_monthly_candle_time_consistency_accepts_calendar_boundaries(month_start, month_end):
    opened = int(datetime.fromisoformat(month_start).timestamp() * 1000)
    closed = int(datetime.fromisoformat(month_end).timestamp() * 1000)
    assert api._candle_time_consistent(_row(opened, closed), "1M")


def test_monthly_candle_time_consistency_rejects_non_month_start_and_wrong_close():
    opened = int(datetime(2024, 2, 2, tzinfo=timezone.utc).timestamp() * 1000)
    assert not api._candle_time_consistent(_row(opened, opened + 29 * 86_400_000 - 1), "1M")
    opened = int(datetime(2024, 2, 1, tzinfo=timezone.utc).timestamp() * 1000)
    assert not api._candle_time_consistent(_row(opened, opened + 31 * 86_400_000 - 1), "1M")

def test_candle_time_consistency_rejects_materially_future_open_time():
    now_ms = 1_700_000_000_000
    row = _row(now_ms + 60_001, now_ms + 60_001 + 3_600_000 - 1)
    assert not api._candle_time_consistent(row, "1h", now_ms=now_ms)


def test_candle_time_consistency_allows_small_clock_skew():
    now_ms = 1_700_000_000_000
    opened = now_ms + 60_000
    row = _row(opened, opened + 3_600_000 - 1)
    assert api._candle_time_consistent(row, "1h", now_ms=now_ms)

@pytest.mark.parametrize(
    "opened, expected",
    [
        ("2024-01-01T00:00:00+00:00", True),  # Monday UTC
        ("2024-01-02T00:00:00+00:00", False), # Tuesday UTC
        ("2024-01-01T00:01:00+00:00", False), # Not midnight UTC
    ],
)
def test_weekly_candle_requires_monday_midnight_utc(opened, expected):
    open_ms = int(datetime.fromisoformat(opened).timestamp() * 1000)
    row = _row(open_ms, open_ms + 7 * 86_400_000 - 1)
    assert api._candle_time_consistent(row, "1w", now_ms=open_ms) is expected


def test_three_day_candle_checks_duration_without_assuming_epoch_anchor():
    opened = int(datetime(2024, 1, 2, 12, tzinfo=timezone.utc).timestamp() * 1000)
    row = _row(opened, opened + 3 * 86_400_000 - 1)
    assert api._candle_time_consistent(row, "3d", now_ms=opened)
    row["close_time"] -= 1
    assert not api._candle_time_consistent(row, "3d", now_ms=opened)

