"""Offline safety and contract tests for public market candle endpoints."""
import unittest
import urllib.error
from unittest.mock import patch

from fastapi import HTTPException

import cin_public_market_candles_api as api

SAMPLE = [
    {"open_time": 1700000000000 + i * 3600000, "open": 100 + i, "high": 102 + i,
     "low": 99 + i, "close": 101 + i, "volume": 10.0,
     "close_time": 1700003599999 + i * 3600000}
    for i in range(50)
]


class PublicMarketCandleTests(unittest.IsolatedAsyncioTestCase):
    async def test_candle_endpoint_returns_provenance_and_timestamps(self):
        with patch.object(api, "_load", return_value=SAMPLE):
            result = await api.get_market_candles("BTCUSDT", "1h", 50)
        self.assertEqual(result["mode"], "read_only")
        self.assertEqual(result["source"], "Binance public market-data API")
        self.assertEqual(result["count"], 50)
        self.assertIn("open_time_utc", result["data"][0])
        self.assertIn("close_time_utc", result["data"][0])
        self.assertIn("retrieved_at", result)

    async def test_market_analysis_uses_source_candles_and_labels_limitations(self):
        with patch.object(api, "_load", return_value=SAMPLE):
            result = await api.analyze_public_market("BTCUSDT", "1h", 50)
        self.assertEqual(result["mode"], "read_only")
        self.assertEqual(result["input"]["symbol"], "BTCUSDT")
        self.assertEqual(result["input"]["timeframe"], "1h")
        self.assertEqual(result["input"]["source"], "Binance public market-data API")
        self.assertEqual(result["input"]["candle_count"], 50)
        self.assertTrue(any("not independently audited" in item for item in result["limitations"]))

    async def test_451_falls_back_to_kraken_and_labels_source(self):
        import asyncio
        with patch.object(api, "_fetch_binance", side_effect=urllib.error.HTTPError(
            api.BINANCE_KLINES_URL, 451, "unavailable for legal reasons", {}, None
        )), patch.object(api, "_fetch_kraken", return_value=[dict(SAMPLE[0])]):
            rows = await api._load("BTCUSDT", "1h", 5)
        self.assertEqual(rows[0]["_source"], "Kraken public OHLC API (fallback after Binance HTTP 451)")
        self.assertEqual(rows[0]["_source_endpoint"], api.KRAKEN_OHLC_URL)

    async def test_451_and_fallback_failure_returns_clear_503(self):
        with patch.object(api, "_fetch_binance", side_effect=urllib.error.HTTPError(
            api.BINANCE_KLINES_URL, 451, "unavailable for legal reasons", {}, None
        )), patch.object(api, "_fetch_kraken", side_effect=ValueError("unsupported pair")):
            with self.assertRaises(HTTPException) as ctx:
                await api._load("BTCUSDT", "1h", 5)
        self.assertEqual(ctx.exception.status_code, 503)
        self.assertIn("Kraken fallback", ctx.exception.detail)

    async def test_rejects_bad_symbol(self):
        with self.assertRaises(HTTPException) as ctx:
            await api.get_market_candles("BTC/USDT", "1h", 50)
        self.assertEqual(ctx.exception.status_code, 400)

    async def test_rejects_unsupported_interval(self):
        with self.assertRaises(HTTPException) as ctx:
            await api.get_market_candles("BTCUSDT", "17m", 50)
        self.assertEqual(ctx.exception.status_code, 400)

    async def test_provider_rate_limit_is_safe_503(self):
        with patch.object(api, "_fetch_binance", side_effect=urllib.error.HTTPError(
            api.BINANCE_KLINES_URL, 429, "rate limited", {}, None
        )):
            with self.assertRaises(HTTPException) as ctx:
                await api._load("BTCUSDT", "1h", 50)
        self.assertEqual(ctx.exception.status_code, 503)


if __name__ == "__main__":
    unittest.main()
    def test_public_candle_routes_use_absolute_end_symbol_pattern(self):
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(api.router)
        schema = app.openapi()["paths"]
        for route in ("/market-candles", "/technical-analysis/market"):
            parameters = schema[route]["get"]["parameters"]
            symbol = next(parameter for parameter in parameters if parameter["name"] == "symbol")
            self.assertEqual(symbol["schema"]["pattern"], r"^[A-Za-z0-9]+\z")

