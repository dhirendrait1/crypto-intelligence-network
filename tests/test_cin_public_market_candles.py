"""Offline safety and contract tests for public market candle endpoints."""
import unittest
import urllib.error
from datetime import datetime, timezone
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
    def test_request_json_accepts_provider_response_within_size_limit(self):
        import json

        class Response:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self, size=-1):
                return json.dumps({"ok": True}).encode("utf-8")

        with patch.object(api.urllib.request, "urlopen", return_value=Response()):
            self.assertEqual(api._request_json("https://provider.example/data"), {"ok": True})

    def test_request_json_rejects_oversized_provider_response_before_json_parse(self):
        class Response:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self, size=-1):
                self.requested_size = size
                return b"x" * size

        response = Response()
        with patch.object(api.urllib.request, "urlopen", return_value=response):
            with self.assertRaisesRegex(ValueError, "exceeded the configured size limit"):
                api._request_json("https://provider.example/data")
        self.assertEqual(response.requested_size, api._MAX_PROVIDER_RESPONSE_BYTES + 1)

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

    async def test_rejects_symbol_with_trailing_newline(self):
        with self.assertRaises(HTTPException) as ctx:
            await api.get_market_candles("BTCUSDT\n", "1h", 50)
        self.assertEqual(ctx.exception.status_code, 400)

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


    def test_public_candle_routes_use_absolute_end_symbol_pattern(self):
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(api.router)
        schema = app.openapi()["paths"]
        for route in ("/market-candles", "/technical-analysis/market"):
            parameters = schema[route]["get"]["parameters"]
            symbol = next(parameter for parameter in parameters if parameter["name"] == "symbol")
            self.assertEqual(symbol["schema"]["pattern"], "^[A-Za-z0-9]+$")


    def test_binance_skips_rows_with_boolean_timestamps(self):
        valid = [1700000000000, "100", "105", "98", "102", "12.5", 1700003599999]
        malformed = [True, "100", "105", "98", "102", "12.5", 1700003599999]
        with patch.object(api, "_request_json", return_value=[malformed, valid]):
            rows = api._fetch_binance("BTCUSDT", "1h", 5)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["open_time"], valid[0])

    def test_binance_skips_boolean_ohlcv_values(self):
        valid = [1700000000000, "100", "105", "98", "102", "12.5", 1700003599999]
        malformed = [1700000000000, True, "105", "98", "102", "12.5", 1700003599999]
        with patch.object(api, "_request_json", return_value=[malformed, valid]):
            rows = api._fetch_binance("BTCUSDT", "1h", 5)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["open"], 100.0)

    def test_binance_skips_string_timestamps(self):
        valid = [1700000000000, "100", "105", "98", "102", "12.5", 1700003599999]
        malformed = ["1700000000000", "100", "105", "98", "102", "12.5", 1700003599999]
        with patch.object(api, "_request_json", return_value=[malformed, valid]):
            rows = api._fetch_binance("BTCUSDT", "1h", 5)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["open_time"], valid[0])

    def test_kraken_skips_rows_with_boolean_timestamps(self):
        valid = [1700000000, "100", "105", "98", "102", "101", "12.5", 7]
        malformed = [True, "100", "105", "98", "102", "101", "12.5", 7]
        payload = {"error": [], "result": {"XXBTZUSD": [malformed, valid], "last": 1700000000}}
        with patch.object(api, "_request_json", return_value=payload):
            rows = api._fetch_kraken("BTCUSD", "1h", 5)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["open_time"], valid[0] * 1000)

    def test_binance_rejects_more_candles_than_requested_limit(self):
        payload = [
            [1700000000000 + i * 3600000, "100", "105", "98", "102", "12.5",
             1700003599999 + i * 3600000]
            for i in range(6)
        ]
        with patch.object(api, "_request_json", return_value=payload):
            with self.assertRaisesRegex(ValueError, "more candles than the requested limit"):
                api._fetch_binance("BTCUSDT", "1h", 5)

    def test_kraken_fallback_parses_alternate_xbt_usd_pair_key(self):
        payload = {
            "error": [],
            "result": {
                "XXBTZUSD": [[1700000000, "100", "105", "98", "102", "101", "12.5", 7]],
                "last": 1700000000,
            },
        }
        with patch.object(api, "_request_json", return_value=payload) as request_json:
            rows = api._fetch_kraken("BTCUSD", "1h", 5)
        self.assertIn("pair=XBTUSD", request_json.call_args.args[0])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["_provider_quote_currency"], "USD")
        self.assertEqual(rows[0]["_provider_pair_key"], "XXBTZUSD")
        self.assertEqual(rows[0]["volume"], 12.5)
        self.assertEqual(rows[0]["close_time"], rows[0]["open_time"] + 3_600_000 - 1)

    def test_kraken_fallback_parses_usdt_pair_key(self):
        payload = {
            "error": [],
            "result": {
                "XBTUSDT": [[1700000000, "100", "105", "98", "102", "101", "12.5", 7]],
                "last": 1700000000,
            },
        }
        with patch.object(api, "_request_json", return_value=payload) as request_json:
            rows = api._fetch_kraken("BTCUSDT", "1h", 5)
        self.assertIn("pair=XBTUSDT", request_json.call_args.args[0])
        self.assertEqual(rows[0]["_provider_quote_currency"], "USDT")
        self.assertEqual(rows[0]["_provider_pair_key"], "XBTUSDT")

    def test_kraken_applies_limit_after_filtering_malformed_rows(self):
        valid_rows = [
            [1700000000 + i * 3600, "100", "105", "98", "102", "101", "12.5", 7]
            for i in range(6)
        ]
        malformed_tail = [True, "100", "105", "98", "102", "101", "12.5", 7]
        payload = {
            "error": [],
            "result": {"XXBTZUSD": valid_rows + [malformed_tail], "last": 1700000000},
        }
        with patch.object(api, "_request_json", return_value=payload):
            rows = api._fetch_kraken("BTCUSD", "1h", 5)
        self.assertEqual(len(rows), 5)
        self.assertEqual(rows[0]["open_time"], valid_rows[1][0] * 1000)
        self.assertEqual(rows[-1]["open_time"], valid_rows[-1][0] * 1000)

    def test_kraken_skips_boolean_ohlcv_values(self):
        valid = [1700000000, "100", "105", "98", "102", "101", "12.5", 7]
        malformed = [1700000000, True, "105", "98", "102", "101", "12.5", 7]
        payload = {"error": [], "result": {"XXBTZUSD": [malformed, valid], "last": 1700000000}}
        with patch.object(api, "_request_json", return_value=payload):
            rows = api._fetch_kraken("BTCUSD", "1h", 5)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["open"], 100.0)

    def test_kraken_skips_string_and_fractional_timestamps(self):
        valid = [1700000000, "100", "105", "98", "102", "101", "12.5", 7]
        malformed_string = ["1700000000", "100", "105", "98", "102", "101", "12.5", 7]
        malformed_fractional = [1700000000.5, "100", "105", "98", "102", "101", "12.5", 7]
        payload = {
            "error": [],
            "result": {"XXBTZUSD": [malformed_string, malformed_fractional, valid], "last": 1700000000},
        }
        with patch.object(api, "_request_json", return_value=payload):
            rows = api._fetch_kraken("BTCUSD", "1h", 5)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["open_time"], valid[0] * 1000)

    def test_clean_candles_deduplicates_identical_rows_for_same_open_time(self):
        row = dict(SAMPLE[0])
        cleaned = api._clean_candles([row, dict(row)], "test provider")
        self.assertEqual(cleaned, [row])

    def test_clean_candles_rejects_conflicting_rows_for_same_open_time(self):
        first = dict(SAMPLE[0])
        conflicting = dict(first, close=first["close"] + 0.5)
        with self.assertRaisesRegex(ValueError, "conflicting candles for the same open timestamp"):
            api._clean_candles([first, conflicting], "test provider")

    def test_kraken_fallback_rejects_malformed_response_shape(self):
        with patch.object(api, "_request_json", return_value={"error": [], "result": []}):
            with self.assertRaises(ValueError):
                api._fetch_kraken("BTCUSD", "1h", 5)

    def test_kraken_fallback_rejects_unexpected_pair_identity(self):
        payload = {
            "error": [],
            "result": {
                "XETHZUSD": [[1700000000, "100", "105", "98", "102", "101", "12.5", 7]],
                "last": 1700000000,
            },
        }
        with patch.object(api, "_request_json", return_value=payload):
            with self.assertRaisesRegex(ValueError, "different trading pair"):
                api._fetch_kraken("BTCUSD", "1h", 5)

    def test_kraken_fallback_rejects_ambiguous_multiple_pair_keys(self):
        payload = {
            "error": [],
            "result": {
                "XXBTZUSD": [[1700000000, "100", "105", "98", "102", "101", "12.5", 7]],
                "XETHZUSD": [[1700000000, "100", "105", "98", "102", "101", "12.5", 7]],
                "last": 1700000000,
            },
        }
        with patch.object(api, "_request_json", return_value=payload):
            with self.assertRaisesRegex(ValueError, "exactly one requested trading pair"):
                api._fetch_kraken("BTCUSD", "1h", 5)

    def test_kraken_fallback_rejects_same_base_with_wrong_quote_currency(self):
        payload = {
            "error": [],
            "result": {
                "XXBTZUSD": [[1700000000, "100", "105", "98", "102", "101", "12.5", 7]],
                "last": 1700000000,
            },
        }
        with patch.object(api, "_request_json", return_value=payload):
            with self.assertRaisesRegex(ValueError, "different trading pair"):
                api._fetch_kraken("BTCUSDT", "1h", 5)



    async def test_market_analysis_excludes_forming_candle(self):
        rows = [dict(row) for row in SAMPLE]
        import time
        rows[-1]["close_time"] = int(time.time() * 1000) + 60_000
        with patch.object(api, "_load", return_value=rows):
            result = await api.analyze_public_market("BTCUSDT", "1h", 50)
        self.assertEqual(result["input"]["candles_requested"], 50)
        self.assertEqual(result["input"]["candles_used"], 49)
        self.assertEqual(result["input"]["forming_candles_excluded"], 1)
        self.assertTrue(result["input"]["closed_candles_only"])
        self.assertEqual(result["input"]["candle_count"], 49)

    async def test_market_analysis_returns_422_when_fewer_than_five_candles_are_closed(self):
        rows = [dict(row) for row in SAMPLE[:5]]
        import time
        future_close = int(time.time() * 1000) + 60_000
        for row in rows:
            row["close_time"] = future_close
        with patch.object(api, "_load", return_value=rows):
            with self.assertRaises(HTTPException) as ctx:
                await api.analyze_public_market("BTCUSDT", "1h", 5)
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertIn("Fewer than 5 completed candles", ctx.exception.detail)


    async def test_monthly_freshness_limitations_match_calendar_aware_implementation(self):
        with patch.object(api, "_load", return_value=[dict(row) for row in SAMPLE]):
            candles = await api.get_market_candles("BTCUSDT", "1M", 50)
            analysis = await api.analyze_public_market("BTCUSDT", "1M", 50)

        for limitations in (candles["limitations"], analysis["limitations"]):
            joined = " ".join(limitations)
            self.assertIn("monthly intervals use calendar-month duration", joined)
            self.assertNotIn("31-day approximation", joined)

    async def test_candle_endpoint_marks_forming_rows_and_warns_when_no_closed_candle_exists(self):
        import time
        rows = [dict(row) for row in SAMPLE[:5]]
        future_close = int(time.time() * 1000) + 60_000
        for row in rows:
            row["close_time"] = future_close
        with patch.object(api, "_load", return_value=rows):
            result = await api.get_market_candles("BTCUSDT", "1h", 5)
        self.assertEqual(result["count"], 5)
        self.assertTrue(all(row["is_closed"] is False for row in result["data"]))
        self.assertTrue(all(row["candle_status"] == "forming" for row in result["data"]))
        self.assertIsNone(result["freshness"]["latest_closed_candle_close_time_utc"])
        self.assertIsNotNone(result["freshness"]["stale_data_warning"])


    def test_openapi_documents_runtime_error_statuses_for_both_routes(self):
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(api.router)
        paths = app.openapi()["paths"]

        candle_responses = paths["/market-candles"]["get"]["responses"]
        self.assertTrue({"200", "400", "422", "502", "503"}.issubset(candle_responses))

        analysis_responses = paths["/technical-analysis/market"]["get"]["responses"]
        self.assertTrue({"200", "400", "422", "502", "503"}.issubset(analysis_responses))

    def test_request_schema_and_semantic_validation_match_contract(self):
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(api.router)
        paths = app.openapi()["paths"]

        # Request-schema constraints are exposed in OpenAPI and FastAPI maps
        # these validation failures to HTTP 422.
        for route in ("/market-candles", "/technical-analysis/market"):
            parameters = paths[route]["get"]["parameters"]
            symbol = next(parameter for parameter in parameters if parameter["name"] == "symbol")
            limit = next(parameter for parameter in parameters if parameter["name"] == "limit")
            self.assertEqual(symbol["schema"]["minLength"], 5)
            self.assertEqual(symbol["schema"]["maxLength"], 20)
            self.assertEqual(symbol["schema"]["pattern"], "^[A-Za-z0-9]+$")
            self.assertEqual(limit["schema"]["minimum"], 5)
            self.assertEqual(limit["schema"]["maximum"], 500)
            self.assertIn("422", paths[route]["get"]["responses"])
            self.assertEqual(
                paths[route]["get"]["responses"]["400"]["description"],
                "Unsupported interval or semantic parameter validation failure.",
            )
            self.assertTrue(paths[route]["get"]["responses"]["422"]["description"])

        # Semantic validation inside the handler intentionally uses HTTP 400.
        with self.assertRaises(HTTPException) as ctx:
            api._validate("BTCUSDT", "17m", 50)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(ctx.exception.detail, "Unsupported interval.")


if __name__ == "__main__":
    unittest.main()

def test_binance_filters_materially_future_dated_candles():
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    valid_open = now_ms - (now_ms % 3_600_000) - 3_600_000
    future_open = now_ms + 120_000
    valid = [valid_open, "100", "105", "98", "102", "12.5", valid_open + 3_600_000 - 1]
    future = [future_open, "100", "105", "98", "102", "12.5", future_open + 3_600_000 - 1]
    with patch.object(api, "_request_json", return_value=[valid, future]):
        rows = api._fetch_binance("BTCUSDT", "1h", 5)
    assert len(rows) == 1
    assert rows[0]["open_time"] == valid_open
