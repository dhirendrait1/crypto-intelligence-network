"""Offline safety and contract tests for public market candle endpoints."""
import unittest
import urllib.error
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

import cin_public_market_candles_api as api

SAMPLE = [
    {"open_time": 1700000000000 + i * 3600000, "open": 100 + i, "high": 102 + i,
     "low": 99 + i, "close": 101 + i, "volume": 10.0,
     "close_time": 1700003599999 + i * 3600000}
    for i in range(50)
]


class PublicMarketCandleTests(unittest.IsolatedAsyncioTestCase):
    async def test_provider_response_size_is_bounded(self):
        response = MagicMock()
        response.status = 200
        response.__enter__.return_value = response
        response.read.return_value = b"x" * (api.MAX_PROVIDER_RESPONSE_BYTES + 1)
        with patch.object(api.urllib.request, "urlopen", return_value=response):
            with self.assertRaisesRegex(ValueError, "exceeded the configured size limit"):
                api._request_json("https://example.test/data")
        response.read.assert_called_once_with(api.MAX_PROVIDER_RESPONSE_BYTES + 1)

    async def test_binance_skips_nonfinite_and_impossible_candles(self):
        payload = [
            [1700000000000, "100", "102", "99", "101", "10", 1700003599999],
            [1700003600000, "100", "99", "101", "100", "10", 1700007199999],
            [1700007200000, "100", "NaN", "99", "101", "10", 1700010799999],
            [1700010800000, "100", "102", "99", "101", "Infinity", 1700014399999],
        ]
        with patch.object(api, "_request_json", return_value=payload):
            rows = api._fetch_binance("BTCUSDT", "1h", 5)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["close"], 101.0)

    async def test_kraken_fills_limit_from_valid_rows_when_tail_row_is_invalid(self):
        rows = [
            [1700000000 + i * 3600, "100", "102", "99", "101", "100.5", "10", 4]
            for i in range(6)
        ]
        # The newest provider row is malformed; earlier valid rows should fill the limit.
        rows[-1] = [1700018000, "100", "99", "101", "100", "100", "10", 4]
        payload = {"error": [], "result": {"XBTUSDT": rows, "last": 1700018000}}
        with patch.object(api, "_request_json", return_value=payload):
            candles = api._fetch_kraken("BTCUSDT", "1h", 5)
        self.assertEqual(len(candles), 5)
        self.assertEqual(candles[-1]["open_time"], 1700014400000)

    async def test_kraken_skips_fractional_and_boolean_timestamps(self):
        rows = [
            [1700000000.5, "100", "102", "99", "101", "100.5", "10", 4],
            [True, "100", "102", "99", "101", "100.5", "10", 4],
            [1700000000, "100", "102", "99", "101", "100.5", "10", 4],
        ]
        payload = {"error": [], "result": {"XBTUSDT": rows, "last": 1700000000}}
        with patch.object(api, "_request_json", return_value=payload):
            candles = api._fetch_kraken("BTCUSDT", "1h", 5)
        self.assertEqual(len(candles), 1)
        self.assertEqual(candles[0]["open_time"], 1700000000000)

    async def test_binance_skips_fractional_and_boolean_timestamps(self):
        payload = [
            [1700000000000.5, "100", "102", "99", "101", "10", 1700003599999],
            [True, "100", "102", "99", "101", "10", 1700003599999],
            [1700000000000, "100", "102", "99", "101", "10", 1700003599999],
        ]
        with patch.object(api, "_request_json", return_value=payload):
            rows = api._fetch_binance("BTCUSDT", "1h", 5)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["open_time"], 1700000000000)

    async def test_binance_rejects_more_rows_than_requested(self):
        payload = [
            [1700000000000 + i * 3600000, "100", "102", "99", "101", "10",
             1700003599999 + i * 3600000]
            for i in range(6)
        ]
        with patch.object(api, "_request_json", return_value=payload):
            with self.assertRaisesRegex(ValueError, "more candles than requested"):
                api._fetch_binance("BTCUSDT", "1h", 5)

    async def test_binance_skips_timestamps_outside_datetime_range(self):
        payload = [
            [10**30, "100", "102", "99", "101", "10", 10**30 + 3600000],
            [1700000000000, "100", "102", "99", "101", "10", 1700003599999],
        ]
        with patch.object(api, "_request_json", return_value=payload):
            rows = api._fetch_binance("BTCUSDT", "1h", 5)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["open_time"], 1700000000000)

    async def test_binance_fails_when_all_candles_are_invalid(self):
        payload = [[1700000000000, "100", "99", "101", "100", "10", 1700003599999]]
        with patch.object(api, "_request_json", return_value=payload):
            with self.assertRaisesRegex(ValueError, "no valid candles"):
                api._fetch_binance("BTCUSDT", "1h", 5)

    async def test_load_sorts_out_of_order_candles_chronologically(self):
        reversed_rows = [dict(SAMPLE[2]), dict(SAMPLE[0]), dict(SAMPLE[1])]
        with patch.object(api, "_fetch_binance", return_value=reversed_rows):
            rows = await api._load("BTCUSDT", "1h", 5)
        self.assertEqual([row["open_time"] for row in rows], sorted(row["open_time"] for row in rows))

    async def test_load_rejects_duplicate_candle_timestamps(self):
        duplicate_rows = [dict(SAMPLE[0]), dict(SAMPLE[0])]
        with patch.object(api, "_fetch_binance", return_value=duplicate_rows):
            with self.assertRaises(HTTPException) as ctx:
                await api._load("BTCUSDT", "1h", 5)
        self.assertEqual(ctx.exception.status_code, 502)
        self.assertIn("ambiguous candle sequence", ctx.exception.detail)

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

    async def test_451_uses_coinbase_when_kraken_fails(self):
        with patch.object(api, "_fetch_binance", side_effect=urllib.error.HTTPError(
            api.BINANCE_KLINES_URL, 451, "unavailable for legal reasons", {}, None
        )), patch.object(api, "_fetch_kraken", side_effect=ValueError("pair unavailable")), patch.object(
            api, "_fetch_coinbase", return_value=[dict(SAMPLE[0])]
        ):
            rows = await api._load("BTCUSDT", "1h", 5)
        self.assertEqual(rows[0]["_source"], "Coinbase Exchange public candles API (fallback after Binance HTTP 451)")
        self.assertEqual(rows[0]["_source_endpoint"], api.COINBASE_CANDLES_URL)

    def test_coinbase_candle_rows_are_normalized_and_sorted(self):
        payload = [
            [1700003600, "99", "103", "101", "102", "12.5"],
            [1700000000, "98", "102", "100", "101", "10.5"],
        ]
        with patch.object(api, "_request_json", return_value=payload):
            rows = api._fetch_coinbase("BTCUSDT", "1h", 5)
        self.assertEqual(len(rows), 2)
        self.assertLess(rows[0]["open_time"], rows[1]["open_time"])
        self.assertEqual(rows[0]["open"], 100.0)
        self.assertEqual(rows[0]["high"], 102.0)
        self.assertEqual(rows[0]["low"], 98.0)
        self.assertEqual(rows[0]["close"], 101.0)
        self.assertEqual(rows[0]["volume"], 10.5)

    async def test_451_and_fallback_failure_returns_clear_503(self):
        with patch.object(api, "_fetch_binance", side_effect=urllib.error.HTTPError(
            api.BINANCE_KLINES_URL, 451, "unavailable for legal reasons", {}, None
        )), patch.object(api, "_fetch_kraken", side_effect=ValueError("unsupported pair")), patch.object(
            api, "_fetch_coinbase", side_effect=ValueError("unsupported product")
        ):
            with self.assertRaises(HTTPException) as ctx:
                await api._load("BTCUSDT", "1h", 5)
        self.assertEqual(ctx.exception.status_code, 503)
        self.assertIn("fallbacks unavailable", ctx.exception.detail)

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
