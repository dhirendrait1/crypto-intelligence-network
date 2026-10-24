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


def test_kraken_fallback_rejects_unsupported_interval_without_network(monkeypatch):
    def unexpected_request(_url):
        raise AssertionError("unsupported interval must be rejected before network access")

    monkeypatch.setattr(api, "_request_json", unexpected_request)
    with pytest.raises(ValueError, match="does not support interval 2h"):
        api._fetch_kraken("BTCUSDT", "2h", 10)


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
