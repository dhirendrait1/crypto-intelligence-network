"""Offline safety and contract tests for public market candle endpoints."""
import unittest
import urllib.error
import urllib.parse
from datetime import datetime
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

import cin_public_market_candles_api as api

SAMPLE = [
    {"open_time": 1699999200000 + i * 3600000, "open": 100 + i, "high": 102 + i,
     "low": 99 + i, "close": 101 + i, "volume": 10.0,
     "close_time": 1700002799999 + i * 3600000}
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


    async def test_kraken_rejects_ohlc_payload_over_documented_720_row_cap(self):
        asset_pairs = {"error": [], "result": {
            "XBTUSDT": {"altname": "XBTUSDT", "wsname": "XBT/USDT", "base": "XXBT", "quote": "USDT"}
        }}
        rows = [[1700000000 + i * 60, "100", "102", "99", "101", "100.5", "10", 4] for i in range(721)]
        ohlc = {"error": [], "result": {"XBTUSDT": rows, "last": 1700043260}}
        with patch.object(api, "_request_json", side_effect=[asset_pairs, ohlc]):
            with self.assertRaisesRegex(ValueError, "documented 720-row cap"):
                api._fetch_kraken("BTCUSDT", "1m", 500)

    async def test_kraken_keeps_forming_tail_but_freshness_uses_last_closed_candle(self):
        asset_pairs = {"error": [], "result": {
            "XBTUSDT": {"altname": "XBTUSDT", "wsname": "XBT/USDT", "base": "XXBT", "quote": "USDT"}
        }}
        current_open = 1700002800  # UTC hour boundary
        rows = [
            [current_open - 3600, "100", "102", "99", "101", "100.5", "10", 4],
            [current_open, "101", "103", "100", "102", "101.5", "5", 2],
        ]
        ohlc = {"error": [], "result": {"XBTUSDT": rows, "last": current_open + 30}}
        with patch.object(api, "_request_json", side_effect=[asset_pairs, ohlc]):
            candles = api._fetch_kraken("BTCUSDT", "1h", 5)
        self.assertEqual(len(candles), 2)
        freshness = api._freshness_metadata(candles, "1h", (current_open + 30) * 1000)
        self.assertEqual(freshness["freshness_status"], "fresh")
        self.assertEqual(
            freshness["latest_closed_candle_close_time_utc"],
            datetime.fromtimestamp((current_open - 1) * 1000, timezone.utc).isoformat(),
        )

    async def test_kraken_resolves_exact_asset_pair_and_verifies_ohlc_key(self):
        rows = [[1700000000, "100", "102", "99", "101", "100.5", "10", 4]]
        asset_pairs = {"error": [], "result": {
            "XXBTZUSD": {"altname": "XBTUSD", "wsname": "XBT/USD", "base": "XXBT", "quote": "ZUSD"}
        }}
        ohlc = {"error": [], "result": {"XXBTZUSD": rows, "last": 1700000000}}
        with patch.object(api, "_request_json", side_effect=[asset_pairs, ohlc]) as request:
            candles = api._fetch_kraken("BTCUSD", "1h", 5)
        self.assertEqual(len(candles), 1)
        self.assertIn("pair=XBTUSD", request.call_args_list[1].args[0])

    async def test_kraken_rejects_asset_pair_quote_mismatch(self):
        asset_pairs = {"error": [], "result": {
            "XXBTZUSD": {"altname": "XBTUSD", "wsname": "XBT/USD", "base": "XXBT", "quote": "ZUSD"}
        }}
        with patch.object(api, "_request_json", return_value=asset_pairs):
            with self.assertRaisesRegex(ValueError, "base/quote identity"):
                api._fetch_kraken("BTCUSDT", "1h", 5)

    async def test_kraken_rejects_ohlc_result_key_not_in_asset_pair_record(self):
        asset_pairs = {"error": [], "result": {
            "XXBTZUSD": {"altname": "XBTUSD", "wsname": "XBT/USD", "base": "XXBT", "quote": "ZUSD"}
        }}
        ohlc = {"error": [], "result": {"XETHZUSD": [[1700000000, "100", "102", "99", "101", "100.5", "10", 4]], "last": 1}}
        with patch.object(api, "_request_json", side_effect=[asset_pairs, ohlc]):
            with self.assertRaisesRegex(ValueError, "did not match the resolved requested market"):
                api._fetch_kraken("BTCUSD", "1h", 5)

    async def test_kraken_rejects_ambiguous_multiple_market_result_keys(self):
        rows = [[1700000000, "100", "102", "99", "101", "100.5", "10", 4]]
        payload = {
            "error": [],
            "result": {"XBTUSDT": rows, "ETHUSDT": rows, "last": 1700000000},
        }
        with patch.object(api, "_request_json", side_effect=[{"error":[],"result":{"XBTUSDT":{"altname":"XBTUSDT","wsname":"XBT/USDT","base":"XXBT","quote":"USDT"}}}, payload]):
            with self.assertRaisesRegex(ValueError, "did not match the resolved requested market"):
                api._fetch_kraken("BTCUSDT", "1h", 5)

    async def test_kraken_accepts_single_market_result_with_cursor_metadata(self):
        rows = [[1700000000, "100", "102", "99", "101", "100.5", "10", 4]]
        payload = {"error": [], "result": {"XBTUSDT": rows, "last": 1700000000}}
        with patch.object(api, "_request_json", side_effect=[{"error":[],"result":{"XBTUSDT":{"altname":"XBTUSDT","wsname":"XBT/USDT","base":"XXBT","quote":"USDT"}}}, payload]):
            candles = api._fetch_kraken("BTCUSDT", "1h", 5)
        self.assertEqual(len(candles), 1)

    async def test_kraken_fills_limit_from_valid_rows_when_tail_row_is_invalid(self):
        rows = [
            [1700000000 + i * 3600, "100", "102", "99", "101", "100.5", "10", 4]
            for i in range(6)
        ]
        # The newest provider row is malformed; earlier valid rows should fill the limit.
        rows[-1] = [1700018000, "100", "99", "101", "100", "100", "10", 4]
        payload = {"error": [], "result": {"XBTUSDT": rows, "last": 1700018000}}
        with patch.object(api, "_request_json", side_effect=[{"error":[],"result":{"XBTUSDT":{"altname":"XBTUSDT","wsname":"XBT/USDT","base":"XXBT","quote":"USDT"}}}, payload]):
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
        asset_pairs = {"error": [], "result": {
            "XBTUSDT": {"altname": "XBTUSDT", "wsname": "XBT/USDT", "base": "XXBT", "quote": "USDT"}
        }}
        with patch.object(api, "_request_json", side_effect=[asset_pairs, payload]):
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

    async def test_binance_rejects_request_limit_above_provider_max_without_request(self):
        with patch.object(api, "_request_json") as request:
            with self.assertRaisesRegex(ValueError, "integer from 1 to 1000"):
                api._fetch_binance("BTCUSDT", "1h", 1001)
        request.assert_not_called()

    async def test_binance_rejects_boolean_or_non_integer_request_limit(self):
        for invalid_limit in (True, 5.5, "5", 0):
            with self.subTest(limit=invalid_limit):
                with patch.object(api, "_request_json") as request:
                    with self.assertRaisesRegex(ValueError, "integer from 1 to 1000"):
                        api._fetch_binance("BTCUSDT", "1h", invalid_limit)
                request.assert_not_called()

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


    def test_coverage_metadata_reports_partial_returned_row_count(self):
        rows = [dict(row) for row in SAMPLE[:3]]
        result = api._coverage_metadata(rows, 5)
        self.assertEqual(result["requested_candle_limit"], 5)
        self.assertEqual(result["returned_candle_count"], 3)
        self.assertEqual(result["candle_count_shortfall"], 2)
        self.assertEqual(result["coverage_status"], "partial")
        self.assertEqual(
            result["coverage_scope"],
            "returned_row_count_against_requested_limit; continuity_is_reported_separately"
        )

    def test_coverage_metadata_reports_complete_count_without_claiming_continuity(self):
        rows = [dict(row) for row in SAMPLE[:5]]
        result = api._coverage_metadata(rows, 5)
        self.assertEqual(result["coverage_status"], "complete")
        self.assertEqual(result["candle_count_shortfall"], 0)
        self.assertIn("continuity_is_reported_separately", result["coverage_scope"])

    async def test_kraken_market_candle_gaps_are_not_labelled_as_feed_loss(self):
        first = dict(SAMPLE[0], _source="Kraken public OHLC API", _source_endpoint=api.KRAKEN_OHLC_URL, _provider="kraken")
        later = dict(SAMPLE[2], _source="Kraken public OHLC API", _source_endpoint=api.KRAKEN_OHLC_URL, _provider="kraken")
        with patch.object(api, "_load", new=AsyncMock(return_value=[first, later])):
            result = await api.get_market_candles("BTCUSDT", "1h", 5)
        integrity = result["timeline_integrity"]
        self.assertTrue(integrity["has_gaps"])
        self.assertEqual(integrity["provider"], "kraken")
        self.assertEqual(integrity["gap_interpretation"], "missing_intervals_may_indicate_no_trades")
        self.assertIn("not proof of feed loss", integrity["interpretation_note"])

    async def test_coinbase_market_candle_gaps_may_reflect_no_trades_not_feed_loss(self):
        first = dict(SAMPLE[0], _source="Coinbase public candles API", _source_endpoint=api.COINBASE_CANDLES_URL, _provider="coinbase")
        later = dict(SAMPLE[2], _source="Coinbase public candles API", _source_endpoint=api.COINBASE_CANDLES_URL, _provider="coinbase")
        with patch.object(api, "_load", new=AsyncMock(return_value=[first, later])):
            result = await api.get_market_candles("BTCUSD", "1h", 5)
        integrity = result["timeline_integrity"]
        self.assertTrue(integrity["has_gaps"])
        self.assertEqual(integrity["provider"], "coinbase")
        self.assertEqual(integrity["gap_interpretation"], "missing_intervals_may_indicate_no_trades")
        self.assertIn("not proof of feed loss", integrity["interpretation_note"])

    async def test_unknown_provider_gap_cause_remains_unclassified(self):
        first = dict(SAMPLE[0], _source="Unknown public source", _source_endpoint="https://example.invalid", _provider="unknown")
        later = dict(SAMPLE[2], _source="Unknown public source", _source_endpoint="https://example.invalid", _provider="unknown")
        with patch.object(api, "_load", new=AsyncMock(return_value=[first, later])):
            result = await api.get_market_candles("BTCUSDT", "1h", 5)
        self.assertEqual(result["timeline_integrity"]["gap_interpretation"], "cause_not_inferred_from_candle_rows")

    async def test_market_candles_reports_partial_provider_response_coverage(self):
        rows = [dict(row) for row in SAMPLE[:3]]
        with patch.object(api, "_load", return_value=rows):
            result = await api.get_market_candles("BTCUSDT", "1h", 5)
        self.assertEqual(result["coverage"]["requested_candle_limit"], 5)
        self.assertEqual(result["coverage"]["returned_candle_count"], 3)
        self.assertEqual(result["coverage"]["candle_count_shortfall"], 2)
        self.assertEqual(result["coverage"]["coverage_status"], "partial")

    async def test_market_analysis_uses_source_candles_and_labels_limitations(self):
        with patch.object(api, "_load", return_value=SAMPLE):
            result = await api.analyze_public_market("BTCUSDT", "1h", 50)
        self.assertEqual(result["mode"], "read_only")
        self.assertEqual(result["input"]["symbol"], "BTCUSDT")
        self.assertEqual(result["input"]["timeframe"], "1h")
        self.assertEqual(result["input"]["source"], "Binance public market-data API")
        self.assertEqual(result["input"]["candle_count"], 50)
        self.assertTrue(any("not independently audited" in item for item in result["limitations"]))

    async def test_market_analysis_excludes_forming_candles_and_reports_freshness(self):
        now_ms = int(api.datetime.now(api.timezone.utc).timestamp() * 1000)
        rows = [
            {
                "open_time": now_ms - (index + 2) * 3_600_000,
                "open": 100 + index,
                "high": 103 + index,
                "low": 99 + index,
                "close": 102 + index,
                "volume": 10.0,
                "close_time": now_ms - (index + 1) * 3_600_000,
            }
            for index in range(5)
        ]
        rows.append({
            "open_time": now_ms - 600_000,
            "open": 105.0,
            "high": 108.0,
            "low": 104.0,
            "close": 107.0,
            "volume": 11.0,
            "close_time": now_ms + 3_000_000,
        })
        with patch.object(api, "_load", return_value=rows):
            result = await api.analyze_public_market("BTCUSDT", "1h", 6)
        self.assertEqual(result["input"]["requested_candle_count"], 6)
        self.assertEqual(result["input"]["analysis_candle_count"], 5)
        self.assertEqual(result["input"]["forming_candle_excluded_count"], 1)
        self.assertIn("earlier than retrieval time", result["input"]["candle_closure_policy"])
        self.assertIn("latest_closed_candle_age_seconds", result["input"])

    async def test_market_analysis_requires_five_completed_candles(self):
        now_ms = int(api.datetime.now(api.timezone.utc).timestamp() * 1000)
        rows = [
            {
                "open_time": now_ms - (index + 2) * 3_600_000,
                "open": 100 + index,
                "high": 103 + index,
                "low": 99 + index,
                "close": 102 + index,
                "volume": 10.0,
                "close_time": now_ms - (index + 1) * 3_600_000 if index < 3 else now_ms + 3_000_000,
            }
            for index in range(5)
        ]
        with patch.object(api, "_load", return_value=rows):
            with self.assertRaises(HTTPException) as ctx:
                await api.analyze_public_market("BTCUSDT", "1h", 5)
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertIn("five completed candles", ctx.exception.detail)

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
            rows = await api._load("BTCUSD", "1h", 5)
        self.assertEqual(rows[0]["_source"], "Coinbase Exchange public candles API (fallback after Binance HTTP 451)")
        self.assertEqual(rows[0]["_source_endpoint"], api.COINBASE_CANDLES_URL)

    async def test_451_usdt_fallback_never_requests_coinbase_usd_product(self):
        with patch.object(api, "_fetch_binance", side_effect=urllib.error.HTTPError(
            api.BINANCE_KLINES_URL, 451, "unavailable for legal reasons", {}, None
        )), patch.object(api, "_fetch_kraken", side_effect=ValueError("pair unavailable")), patch.object(
            api, "_request_json"
        ) as request_json:
            with self.assertRaises(HTTPException) as ctx:
                await api._load("BTCUSDT", "1h", 5)
        self.assertEqual(ctx.exception.status_code, 503)
        self.assertIn("fallbacks unavailable", ctx.exception.detail)
        request_json.assert_not_called()

    def test_coinbase_rejects_usdt_without_substituting_usd(self):
        with patch.object(api, "_request_json") as request_json:
            with self.assertRaisesRegex(ValueError, "USDT requests are not mapped to USD"):
                api._fetch_coinbase("BTCUSDT", "1h", 5)
        request_json.assert_not_called()


    def test_coinbase_rejects_response_over_provider_page_limit(self):
        payload = [[1700000000 + index * 3600, "99", "103", "100", "102", "10"] for index in range(301)]
        with patch.object(api, "_request_json", return_value=payload):
            with self.assertRaisesRegex(ValueError, "exceeded the 300-candle per-request limit"):
                api._fetch_coinbase("BTCUSD", "1h", 5)


    def test_coinbase_pagination_windows_are_granularity_aligned_and_adjacent(self):
        requests = []
        def capture(url):
            requests.append(urllib.parse.urlparse(url).query)
            return []
        with patch.object(api, "_request_json", side_effect=capture):
            api._fetch_coinbase("BTCUSD", "1m", 500)
        self.assertEqual(len(requests), 2)
        first = urllib.parse.parse_qs(requests[0])
        second = urllib.parse.parse_qs(requests[1])
        first_start = int(datetime.fromisoformat(first["start"][0]).timestamp())
        first_end = int(datetime.fromisoformat(first["end"][0]).timestamp())
        second_start = int(datetime.fromisoformat(second["start"][0]).timestamp())
        self.assertEqual(first_start % 60, 0)
        self.assertEqual(second_start % 60, 0)
        self.assertEqual(first_end, second_start)
        self.assertEqual((first_end - first_start) // 60, 300)

    def test_coinbase_excludes_rows_outside_requested_utc_window(self):
        requested_bounds = {}
        def response(url):
            query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
            start_seconds = int(datetime.fromisoformat(query["start"][0]).timestamp())
            end_seconds = int(datetime.fromisoformat(query["end"][0]).timestamp())
            latest_open = (end_seconds // 3600) * 3600
            requested_bounds["start"] = start_seconds * 1000
            requested_bounds["latest_open"] = latest_open * 1000
            def candle(timestamp):
                return [timestamp, "99", "103", "100", "102", "10"]
            return [
                candle(start_seconds - 3600),
                candle(start_seconds),
                candle(latest_open),
                candle(latest_open + 3600),
            ]
        with patch.object(api, "_request_json", side_effect=response):
            rows = api._fetch_coinbase("BTCUSD", "1h", 5)
        opens = [row["open_time"] for row in rows]
        self.assertEqual(opens, [requested_bounds["start"], requested_bounds["latest_open"]])

    def test_coinbase_deduplicates_rows_repeated_at_page_boundaries(self):
        row = [1700000000, "99", "103", "100", "102", "10"]
        with patch.object(api, "_request_json", return_value=[row]):
            rows = api._fetch_coinbase("BTCUSD", "1m", 500)
        self.assertEqual(sum(1 for item in rows if item["open_time"] == 1700000000000), 1)

    def test_coinbase_rejects_conflicting_rows_with_same_open_timestamp(self):
        first = [1700000000, "99", "103", "100", "102", "10"]
        conflicting = [1700000000, "99", "103", "100", "101", "10"]
        with patch.object(api, "_request_json", return_value=[first, conflicting]):
            with self.assertRaisesRegex(
                ValueError, "conflicting candle rows for the same open timestamp"
            ):
                api._fetch_coinbase("BTCUSD", "1m", 500)

    def test_coinbase_paginates_requested_history_in_bounded_chunks(self):
        payload = [[1700000000, "99", "103", "100", "102", "10"]]
        with patch.object(api, "_request_json", return_value=payload) as request:
            rows = api._fetch_coinbase("BTCUSD", "1m", 500)
        self.assertEqual(request.call_count, 2)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["open_time"], 1700000000000)

    def test_coinbase_candle_rows_are_normalized_and_sorted(self):
        payload = [
            [1700003600, "99", "103", "101", "102", "12.5"],
            [1700000000, "98", "102", "100", "101", "10.5"],
        ]
        with patch.object(api, "_request_json", return_value=payload):
            rows = api._fetch_coinbase("BTCUSD", "1h", 5)
        self.assertEqual(len(rows), 2)
        self.assertLess(rows[0]["open_time"], rows[1]["open_time"])
        self.assertEqual(rows[0]["open"], 100.0)
        self.assertEqual(rows[0]["high"], 102.0)
        self.assertEqual(rows[0]["low"], 98.0)
        self.assertEqual(rows[0]["close"], 101.0)
        self.assertEqual(rows[0]["volume"], 10.5)

    def test_coinbase_skips_nonfinite_and_impossible_ohlcv_rows(self):
        payload = [
            [1700000000, "99", "103", "100", "102", "10"],
            [1700003600, "99", "98", "100", "102", "10"],
            [1700007200, "99", "NaN", "100", "102", "10"],
            [1700010800, "99", "103", "100", "102", "Infinity"],
            [1700014400, "99", "103", "100", "NaN", "10"],
        ]
        with patch.object(api, "_request_json", return_value=payload):
            rows = api._fetch_coinbase("BTCUSD", "1h", 5)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["close"], 102.0)

    def test_coinbase_skips_fractional_boolean_and_out_of_range_timestamps(self):
        payload = [
            [1700000000.5, "99", "103", "100", "102", "10"],
            [True, "99", "103", "100", "102", "10"],
            [10**30, "99", "103", "100", "102", "10"],
            [1700000000, "99", "103", "100", "102", "10"],
        ]
        with patch.object(api, "_request_json", return_value=payload):
            rows = api._fetch_coinbase("BTCUSD", "1h", 5)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["open_time"], 1700000000000)

    def test_coinbase_filters_invalid_rows_before_applying_requested_limit(self):
        payload = [
            [1700000000 + i * 3600, "99", "103", "100", "102", "10"]
            for i in range(6)
        ]
        # The newest candle has an impossible OHLC range. It must not consume
        # one of the five requested slots while an older valid row is available.
        payload[-1] = [1700018000, "99", "98", "100", "102", "10"]
        with patch.object(api, "_request_json", return_value=payload):
            rows = api._fetch_coinbase("BTCUSD", "1h", 5)
        self.assertEqual(len(rows), 5)
        self.assertEqual(rows[-1]["open_time"], 1700014400000)

    def test_coinbase_fails_when_all_provider_candles_are_invalid(self):
        payload = [[1700000000, "99", "98", "100", "102", "10"]]
        with patch.object(api, "_request_json", return_value=payload):
            with self.assertRaisesRegex(ValueError, "Coinbase returned no valid candles"):
                api._fetch_coinbase("BTCUSD", "1h", 5)

    def test_cross_provider_comparison_reports_consistent_aligned_candles(self):
        left = [dict(row) for row in SAMPLE[:5]]
        right = [dict(row) for row in SAMPLE[:5]]
        report = api.compare_provider_candles({"Binance": left, "Kraken": right}, "1h")
        self.assertEqual(report["consistency_status"], "consistent_within_configured_tolerances")
        self.assertEqual(report["pairwise_comparisons"][0]["shared_candle_count"], 5)
        self.assertEqual(report["timeline_gap_count"], 0)

    def test_cross_provider_comparison_flags_price_and_volume_discrepancies(self):
        left = [dict(row) for row in SAMPLE[:5]]
        right = [dict(row) for row in SAMPLE[:5]]
        right[2]["close"] *= 1.10
        right[2]["high"] *= 1.10
        right[2]["volume"] *= 3
        report = api.compare_provider_candles(
            {"Binance": left, "Kraken": right}, "1h",
            price_tolerance_bps=25, volume_tolerance_bps=100,
        )
        comparison = report["pairwise_comparisons"][0]
        self.assertFalse(comparison["price_within_tolerance"])
        self.assertFalse(comparison["volume_within_tolerance"])
        self.assertEqual(report["consistency_status"], "discrepancies_or_gaps_detected")

    def test_cross_provider_comparison_reports_missing_timestamps_and_gaps(self):
        left = [dict(row) for row in SAMPLE[:5]]
        right = [dict(row) for row in SAMPLE[:5] if row["open_time"] != SAMPLE[2]["open_time"]]
        right.append({
            "open_time": SAMPLE[5]["open_time"], "open": 105.0, "high": 107.0,
            "low": 104.0, "close": 106.0, "volume": 10.0,
            "close_time": SAMPLE[5]["close_time"],
        })
        report = api.compare_provider_candles({"Binance": left, "Kraken": right}, "1h")
        self.assertEqual(report["providers"]["Kraken"]["missing_timestamp_count"], 1)
        self.assertEqual(report["timeline_gap_count"], 0)
        self.assertEqual(report["provider_missing_interval_count"], 1)
        self.assertEqual(report["consistency_status"], "discrepancies_or_gaps_detected")


    def test_cross_provider_comparison_counts_calendar_month_gaps_exactly(self):
        def month_open(year, month):
            return int(api.datetime(year, month, 1, tzinfo=api.timezone.utc).timestamp() * 1000)
        def candle(year, month):
            start = month_open(year, month)
            end = start + api._interval_duration_ms("1M", start) - 1
            return {"open_time": start, "close_time": end, "open": 100.0,
                    "high": 102.0, "low": 99.0, "close": 101.0, "volume": 10.0}
        rows = [candle(2025, 1), candle(2025, 4), candle(2025, 10)]
        report = api.compare_provider_candles({"Binance": rows, "Kraken": [dict(row) for row in rows]}, "1M")
        self.assertEqual(report["timeline_gap_count"], 2)
        self.assertEqual([gap["missing_intervals"] for gap in report["timeline_gaps"]], [2, 5])

    def test_cross_provider_comparison_rejects_off_grid_month_boundary(self):
        def month_open(year, month):
            return int(api.datetime(year, month, 1, tzinfo=api.timezone.utc).timestamp() * 1000)
        january = month_open(2025, 1)
        off_grid = january + 45 * 86_400_000
        def candle(start):
            end = start + api._interval_duration_ms("1M", start) - 1
            return {"open_time": start, "close_time": end, "open": 100.0,
                    "high": 102.0, "low": 99.0, "close": 101.0, "volume": 10.0}
        with self.assertRaisesRegex(ValueError, "do not align"):
            api.compare_provider_candles(
                {"Binance": [candle(january), candle(off_grid)],
                 "Kraken": [candle(january), candle(off_grid)]}, "1M"
            )


    def test_timeline_integrity_rejects_overlapping_and_duplicate_opens(self):
        first = dict(SAMPLE[0])
        overlapping = dict(SAMPLE[1], open_time=first["open_time"] + 1)
        with self.assertRaisesRegex(ValueError, "overlapping"):
            api._timeline_integrity_metadata([first, overlapping], "1h")
        with self.assertRaisesRegex(ValueError, "overlapping"):
            api._timeline_integrity_metadata([first, dict(first)], "1h")

    def test_timeline_integrity_rejects_invalid_open_timestamp(self):
        with self.assertRaisesRegex(ValueError, "invalid candle open timestamp"):
            api._timeline_integrity_metadata([{"open_time": True}], "1h")

    def test_provider_comparison_validates_duration_and_known_provider_boundaries(self):
        malformed = dict(SAMPLE[0], close_time=SAMPLE[0]["close_time"] - 1)
        with self.assertRaisesRegex(ValueError, "invalid timeframe duration"):
            api.compare_provider_candles(
                {"Binance": [malformed], "Kraken": [dict(SAMPLE[0])]}, "1h"
            )
        monday = int(api.datetime(2025, 1, 6, tzinfo=api.timezone.utc).timestamp() * 1000)
        candle = {"open_time": monday, "close_time": monday + 604_800_000 - 1,
                  "open": 100.0, "high": 102.0, "low": 99.0, "close": 101.0, "volume": 10.0}
        thursday = monday + 3 * 86_400_000
        kraken_candle = dict(candle, open_time=thursday, close_time=thursday + 604_800_000 - 1)
        with self.assertRaisesRegex(ValueError, "provider timeframe boundary"):
            api.compare_provider_candles(
                {"Binance": [candle], "Kraken": [candle]}, "1w"
            )
        # Arbitrary labels remain usable without inventing a provider-specific weekly anchor.
        report = api.compare_provider_candles(
            {"Feed A": [candle], "Feed B": [dict(candle)]}, "1w"
        )
        self.assertEqual(report["provider_count"], 2)

    def test_provider_comparison_checks_kraken_thursday_weekly_anchor(self):
        thursday = int(api.datetime(2025, 1, 9, tzinfo=api.timezone.utc).timestamp() * 1000)
        candle = {"open_time": thursday, "close_time": thursday + 604_800_000 - 1,
                  "open": 100.0, "high": 102.0, "low": 99.0, "close": 101.0, "volume": 10.0}
        report = api.compare_provider_candles(
            {"Kraken": [candle], "Other": [dict(candle)]}, "1w"
        )
        self.assertEqual(report["provider_count"], 2)

    def test_cross_provider_comparison_rejects_mismatched_provider_provenance(self):
        binance_row = dict(SAMPLE[0], _provider="kraken")
        kraken_row = dict(SAMPLE[0], _provider="kraken")
        with self.assertRaisesRegex(ValueError, "mismatched provider provenance"):
            api.compare_provider_candles(
                {"Binance": [binance_row], "Kraken": [kraken_row]}, "1h"
            )

    def test_cross_provider_comparison_accepts_matching_provider_provenance(self):
        binance_row = dict(SAMPLE[0], _provider="binance")
        kraken_row = dict(SAMPLE[0], _provider="kraken")
        report = api.compare_provider_candles(
            {"Binance": [binance_row], "Kraken": [kraken_row]}, "1h"
        )
        self.assertEqual(report["consistency_status"], "consistent_within_configured_tolerances")

    def test_cross_provider_comparison_rejects_mismatched_base_quote_identity(self):
        with self.assertRaisesRegex(ValueError, "base/quote assets differ"):
            api.compare_provider_candles(
                {"Binance": [dict(SAMPLE[0])], "Kraken": [dict(SAMPLE[0])]}, "1h",
                market_identity_by_provider={
                    "Binance": {"base_asset": "BTC", "quote_asset": "USDT"},
                    "Kraken": {"base_asset": "BTC", "quote_asset": "USD"},
                },
            )

    def test_cross_provider_comparison_accepts_matching_market_identity(self):
        report = api.compare_provider_candles(
            {"Binance": [dict(SAMPLE[0])], "Kraken": [dict(SAMPLE[0])]}, "1h",
            market_identity_by_provider={
                "Binance": {"base_asset": "BTC", "quote_asset": "USD"},
                "Kraken": {"base_asset": "BTC", "quote_asset": "USD"},
            },
        )
        self.assertTrue(report["market_identity"]["verified_across_inputs"])
        self.assertEqual(report["market_identity"]["quote_asset"], "USD")

    def test_cross_provider_comparison_requires_identity_for_each_provider(self):
        with self.assertRaisesRegex(ValueError, "match the compared provider names"):
            api.compare_provider_candles(
                {"Binance": [dict(SAMPLE[0])], "Kraken": [dict(SAMPLE[0])]}, "1h",
                market_identity_by_provider={
                    "Binance": {"base_asset": "BTC", "quote_asset": "USD"}
                },
            )

    def test_cross_provider_comparison_rejects_duplicate_or_invalid_rows(self):
        duplicate = [dict(SAMPLE[0]), dict(SAMPLE[0])]
        with self.assertRaisesRegex(ValueError, "duplicate candle timestamps"):
            api.compare_provider_candles({"A": duplicate, "B": [dict(SAMPLE[0])]}, "1h")
        invalid = [dict(SAMPLE[0])]
        invalid[0]["high"] = 1
        with self.assertRaisesRegex(ValueError, "invalid candle"):
            api.compare_provider_candles({"A": invalid, "B": [dict(SAMPLE[0])]}, "1h")

    def test_cross_provider_comparison_requires_two_providers_and_valid_tolerances(self):
        with self.assertRaisesRegex(ValueError, "At least two"):
            api.compare_provider_candles({"A": [dict(SAMPLE[0])]}, "1h")
        with self.assertRaisesRegex(ValueError, "Price tolerance"):
            api.compare_provider_candles(
                {"A": [dict(SAMPLE[0])], "B": [dict(SAMPLE[0])]}, "1h", price_tolerance_bps=float("nan")
            )

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



    async def test_kraken_rate_limits_fail_closed_without_coinbase_fanout(self):
        for code in (418, 429):
            with self.subTest(status=code):
                rate_limit = urllib.error.HTTPError(
                    api.KRAKEN_OHLC_URL, code, "rate limited", {}, None
                )
                with patch.object(api, "_fetch_binance", side_effect=urllib.error.HTTPError(
                    api.BINANCE_KLINES_URL, 451, "unavailable for legal reasons", {}, None
                )), patch.object(api, "_fetch_kraken", side_effect=rate_limit), patch.object(
                    api, "_fetch_coinbase"
                ) as coinbase:
                    with self.assertRaises(HTTPException) as ctx:
                        await api._load("BTCUSD", "1h", 5)
                self.assertEqual(ctx.exception.status_code, 503)
                self.assertEqual(
                    ctx.exception.detail,
                    "Kraken public market-data rate limit reached; retry later."
                )
                coinbase.assert_not_called()

    async def test_coinbase_rate_limit_returns_safe_503_without_retry(self):
        rate_limit = urllib.error.HTTPError(
            api.COINBASE_CANDLES_URL, 429, "rate limited", {}, None
        )
        with patch.object(api, "_fetch_binance", side_effect=urllib.error.HTTPError(
            api.BINANCE_KLINES_URL, 451, "unavailable for legal reasons", {}, None
        )), patch.object(api, "_fetch_kraken", side_effect=ValueError("pair unavailable")), patch.object(
            api, "_fetch_coinbase", side_effect=rate_limit
        ):
            with self.assertRaises(HTTPException) as ctx:
                await api._load("BTCUSD", "1h", 5)
        self.assertEqual(ctx.exception.status_code, 503)
        self.assertIn("Coinbase HTTP 429", ctx.exception.detail)

    async def test_binance_malformed_success_response_fails_closed_without_fallback(self):
        with patch.object(api, "_fetch_binance", side_effect=ValueError("malformed JSON")), patch.object(
            api, "_fetch_kraken"
        ) as kraken, patch.object(api, "_fetch_coinbase") as coinbase:
            with self.assertRaises(HTTPException) as ctx:
                await api._load("BTCUSDT", "1h", 5)
        self.assertEqual(ctx.exception.status_code, 502)
        self.assertEqual(ctx.exception.detail, "Binance public market-data provider returned an invalid response.")
        kraken.assert_not_called()
        coinbase.assert_not_called()

    async def test_market_candles_maps_timeline_integrity_failure_to_safe_502(self):
        rows = [dict(row) for row in SAMPLE[:5]]
        with patch.object(api, "_load", return_value=rows), patch.object(
            api, "_timeline_integrity_metadata", side_effect=ValueError("internal timestamp detail")
        ):
            with self.assertRaises(HTTPException) as ctx:
                await api.get_market_candles("BTCUSDT", "1h", 5)
        self.assertEqual(ctx.exception.status_code, 502)
        self.assertEqual(ctx.exception.detail, "Public market-data provider returned inconsistent candle timeline metadata.")
        self.assertNotIn("internal timestamp detail", ctx.exception.detail)

    async def test_technical_analysis_maps_integrity_failure_to_safe_502(self):
        rows = [dict(row) for row in SAMPLE[:10]]
        with patch.object(api, "_load", return_value=rows), patch.object(
            api, "_timeline_integrity_metadata", side_effect=ValueError("private validation detail")
        ):
            with self.assertRaises(HTTPException) as ctx:
                await api.analyze_public_market("BTCUSDT", "1h", 10)
        self.assertEqual(ctx.exception.status_code, 502)
        self.assertEqual(ctx.exception.detail, "Fetched public candles failed technical-analysis integrity validation.")
        self.assertNotIn("private validation detail", ctx.exception.detail)

    async def test_technical_analysis_sanitizes_analysis_validation_errors(self):
        rows = [dict(row) for row in SAMPLE[:10]]
        with patch.object(api, "_load", return_value=rows), patch.object(
            api, "analyze_ohlc", side_effect=ValueError("internal indicator detail")
        ):
            with self.assertRaises(HTTPException) as ctx:
                await api.analyze_public_market("BTCUSDT", "1h", 10)
        self.assertEqual(ctx.exception.status_code, 502)
        self.assertNotIn("internal indicator detail", ctx.exception.detail)

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


    def test_timeline_integrity_reports_contiguous_candles(self):
        report = api._timeline_integrity_metadata([dict(row) for row in SAMPLE[:5]], "1h")
        self.assertFalse(report["has_gaps"])
        self.assertEqual(report["missing_interval_count"], 0)
        self.assertFalse(report["missing_candles_synthesized"])

    def test_timeline_integrity_counts_multiple_missing_intervals(self):
        report = api._timeline_integrity_metadata([dict(SAMPLE[0]), dict(SAMPLE[1]), dict(SAMPLE[4])], "1h")
        self.assertTrue(report["has_gaps"])
        self.assertEqual(report["gap_count"], 1)
        self.assertEqual(report["missing_interval_count"], 2)
        self.assertEqual(report["gaps"][0]["missing_interval_count"], 2)
        self.assertEqual(report["scope"], "between_returned_candles_only")

    def test_timeline_integrity_counts_calendar_month_gaps(self):
        def month_open(year, month):
            return int(api.datetime(year, month, 1, tzinfo=api.timezone.utc).timestamp() * 1000)
        january, april = month_open(2025, 1), month_open(2025, 4)
        report = api._timeline_integrity_metadata([{"open_time": january}, {"open_time": april}], "1M")
        self.assertEqual(report["missing_interval_count"], 2)
        self.assertEqual(report["gaps"][0]["expected_next_open_time"], month_open(2025, 2))

    def test_freshness_metadata_marks_recent_completed_candle_fresh(self):
        now_ms = 1_700_000_000_000
        rows = [dict(SAMPLE[0])]
        rows[0]["close_time"] = now_ms - 30_000
        result = api._freshness_metadata(rows, "1h", now_ms)
        self.assertEqual(result["freshness_status"], "fresh")
        self.assertFalse(result["is_stale"])
        self.assertIsNone(result["stale_data_warning"])

    def test_freshness_metadata_marks_old_completed_candle_stale(self):
        now_ms = 1_700_000_000_000
        rows = [dict(SAMPLE[0])]
        rows[0]["close_time"] = now_ms - (2 * 3_600_000 + 1)
        result = api._freshness_metadata(rows, "1h", now_ms)
        self.assertEqual(result["freshness_status"], "stale")
        self.assertTrue(result["is_stale"])
        self.assertIn("freshness threshold", result["stale_data_warning"])

    def test_freshness_metadata_distinguishes_forming_only_data(self):
        now_ms = 1_700_000_000_000
        rows = [dict(SAMPLE[0])]
        rows[0]["close_time"] = now_ms + 60_000
        result = api._freshness_metadata(rows, "1h", now_ms)
        self.assertEqual(result["freshness_status"], "no_completed_candle")
        self.assertIsNone(result["is_stale"])
        self.assertIsNone(result["latest_closed_candle_age_seconds"])



    def test_freshness_metadata_rejects_future_open_timestamp(self):
        now_ms = 1_700_000_000_000
        rows = [dict(SAMPLE[0])]
        rows[0]["open_time"] = now_ms + 1
        with self.assertRaisesRegex(ValueError, "future open timestamp"):
            api._freshness_metadata(rows, "1h", now_ms)

    async def test_market_candles_maps_future_open_timestamp_to_safe_502(self):
        now_ms = int(api.datetime.now(api.timezone.utc).timestamp() * 1000)
        rows = [dict(row) for row in SAMPLE[:5]]
        rows[0]["open_time"] = now_ms + 3_600_000
        rows[0]["close_time"] = rows[0]["open_time"] + 3_600_000 - 1
        with patch.object(api, "_load", return_value=rows):
            with self.assertRaises(HTTPException) as ctx:
                await api.get_market_candles("BTCUSDT", "1h", 5)
        self.assertEqual(ctx.exception.status_code, 502)
        self.assertEqual(
            ctx.exception.detail,
            "Public market-data provider returned inconsistent candle timeline metadata."
        )

    async def test_technical_analysis_maps_future_open_timestamp_to_safe_502(self):
        now_ms = int(api.datetime.now(api.timezone.utc).timestamp() * 1000)
        rows = [
            {
                "open_time": now_ms - (index + 2) * 3_600_000,
                "open": 100 + index, "high": 103 + index, "low": 99 + index,
                "close": 102 + index, "volume": 10.0,
                "close_time": now_ms - (index + 1) * 3_600_000,
            }
            for index in range(5)
        ]
        rows.append({
            "open_time": now_ms + 3_600_000, "open": 105.0, "high": 108.0,
            "low": 104.0, "close": 107.0, "volume": 11.0,
            "close_time": now_ms + 2 * 3_600_000 - 1,
        })
        with patch.object(api, "_load", return_value=rows):
            with self.assertRaises(HTTPException) as ctx:
                await api.analyze_public_market("BTCUSDT", "1h", 6)
        self.assertEqual(ctx.exception.status_code, 502)
        self.assertEqual(
            ctx.exception.detail,
            "Public market-data provider returned invalid candle freshness timestamps."
        )

    async def test_binance_timeout_falls_back_to_kraken_and_labels_source(self):
        with patch.object(api, "_fetch_binance", side_effect=TimeoutError("read timed out")), patch.object(
            api, "_fetch_kraken", return_value=[dict(SAMPLE[0])]
        ) as kraken:
            rows = await api._load("BTCUSDT", "1h", 5)
        kraken.assert_called_once_with("BTCUSDT", "1h", 5)
        self.assertIn("fallback after Binance transport failure", rows[0]["_source"])
        self.assertEqual(rows[0]["_source_endpoint"], api.KRAKEN_OHLC_URL)

    async def test_binance_transport_and_kraken_failure_falls_back_to_coinbase(self):
        with patch.object(api, "_fetch_binance", side_effect=urllib.error.URLError("network down")), patch.object(
            api, "_fetch_kraken", side_effect=TimeoutError("kraken timed out")
        ), patch.object(api, "_fetch_coinbase", return_value=[dict(SAMPLE[0])]) as coinbase:
            rows = await api._load("BTCUSD", "1h", 5)
        coinbase.assert_called_once_with("BTCUSD", "1h", 5)
        self.assertIn("fallback after Binance transport failure", rows[0]["_source"])
        self.assertEqual(rows[0]["_source_endpoint"], api.COINBASE_CANDLES_URL)

    async def test_binance_rate_limit_does_not_trigger_fallback_requests(self):
        with patch.object(api, "_fetch_binance", side_effect=urllib.error.HTTPError(
            api.BINANCE_KLINES_URL, 429, "rate limited", {}, None
        )), patch.object(api, "_fetch_kraken") as kraken, patch.object(api, "_fetch_coinbase") as coinbase:
            with self.assertRaises(HTTPException) as ctx:
                await api._load("BTCUSDT", "1h", 5)
        self.assertEqual(ctx.exception.status_code, 503)
        kraken.assert_not_called()
        coinbase.assert_not_called()

    async def test_transient_primary_and_all_fallback_failures_return_safe_503(self):
        with patch.object(api, "_fetch_binance", side_effect=TimeoutError("primary timed out")), patch.object(
            api, "_fetch_kraken", side_effect=ValueError("pair unavailable")
        ), patch.object(api, "_fetch_coinbase", side_effect=ValueError("unsupported quote")):
            with self.assertRaises(HTTPException) as ctx:
                await api._load("BTCUSD", "1h", 5)
        self.assertEqual(ctx.exception.status_code, 503)
        self.assertIn("Binance transport failure", ctx.exception.detail)



    async def test_load_rejects_invalid_ohlcv_row_from_provider(self):
        invalid = dict(SAMPLE[0])
        invalid["high"] = invalid["low"] - 1
        with patch.object(api, "_fetch_binance", return_value=[invalid]):
            with self.assertRaises(HTTPException) as ctx:
                await api._load("BTCUSDT", "1h", 5)
        self.assertEqual(ctx.exception.status_code, 502)
        self.assertIn("ambiguous candle sequence", ctx.exception.detail)

    async def test_load_rejects_overlapping_candle_time_ranges(self):
        first = dict(SAMPLE[0])
        second = dict(SAMPLE[1])
        second["open_time"] = first["open_time"] + 1
        second["close_time"] = first["close_time"] + 3_600_000
        with patch.object(api, "_fetch_binance", return_value=[first, second]):
            with self.assertRaises(HTTPException) as ctx:
                await api._load("BTCUSDT", "1h", 5)
        self.assertEqual(ctx.exception.status_code, 502)
        self.assertIn("ambiguous candle sequence", ctx.exception.detail)

    async def test_load_rejects_candle_duration_mismatched_to_requested_interval(self):
        malformed = dict(SAMPLE[0])
        malformed["close_time"] -= 1
        with patch.object(api, "_fetch_binance", return_value=[malformed]):
            with self.assertRaises(HTTPException) as ctx:
                await api._load("BTCUSDT", "1h", 5)
        self.assertEqual(ctx.exception.status_code, 502)
        self.assertIn("ambiguous candle sequence", ctx.exception.detail)


    def test_weekly_candle_alignment_is_provider_specific(self):
        monday = int(api.datetime(2025, 1, 6, tzinfo=api.timezone.utc).timestamp() * 1000)
        thursday = int(api.datetime(2025, 1, 9, tzinfo=api.timezone.utc).timestamp() * 1000)
        self.assertTrue(api._is_aligned_candle_open(monday, "1w", "binance"))
        self.assertFalse(api._is_aligned_candle_open(thursday, "1w", "binance"))
        self.assertTrue(api._is_aligned_candle_open(thursday, "1w", "kraken"))
        self.assertFalse(api._is_aligned_candle_open(monday, "1w", "kraken"))


    def test_alignment_rejects_unknown_provider_and_unsupported_provider_intervals(self):
        monday = int(api.datetime(2025, 1, 6, tzinfo=api.timezone.utc).timestamp() * 1000)
        thursday = int(api.datetime(2025, 1, 9, tzinfo=api.timezone.utc).timestamp() * 1000)
        self.assertFalse(api._is_aligned_candle_open(monday, "1w", "unknown"))
        self.assertFalse(api._is_aligned_candle_open(monday, "1w", "coinbase"))
        self.assertFalse(api._is_aligned_candle_open(thursday, "1w", "coinbase"))
        self.assertFalse(api._is_aligned_candle_open(monday, "1M", "kraken"))
        self.assertFalse(api._is_aligned_candle_open(monday, "3d", "kraken"))

    def test_coinbase_fallback_uses_explicit_provider_identity(self):
        with patch.object(api, "_fetch_binance", side_effect=urllib.error.URLError("network down")), patch.object(
            api, "_fetch_kraken", side_effect=TimeoutError("kraken timed out")
        ), patch.object(api, "_fetch_coinbase", return_value=[dict(SAMPLE[0])]):
            rows = await api._load("BTCUSD", "1h", 5)
        self.assertIn("Coinbase Exchange public candles API", rows[0]["_source"])
        self.assertEqual(rows[0]["_source_endpoint"], api.COINBASE_CANDLES_URL)

    def test_candle_open_alignment_uses_utc_timeframe_boundaries(self):
        aligned_hour = 1699999200000
        self.assertTrue(api._is_aligned_candle_open(aligned_hour, "1h"))
        self.assertFalse(api._is_aligned_candle_open(aligned_hour + 1, "1h"))
        self.assertTrue(api._is_aligned_candle_open(86_400_000, "1d"))
        self.assertFalse(api._is_aligned_candle_open(86_400_001, "1d"))
        monday = int(api.datetime(2025, 1, 6, tzinfo=api.timezone.utc).timestamp() * 1000)
        self.assertTrue(api._is_aligned_candle_open(monday, "1w"))
        self.assertFalse(api._is_aligned_candle_open(monday + 86_400_000, "1w"))
        month_start = int(api.datetime(2025, 2, 1, tzinfo=api.timezone.utc).timestamp() * 1000)
        self.assertTrue(api._is_aligned_candle_open(month_start, "1M"))
        self.assertFalse(api._is_aligned_candle_open(month_start + 86_400_000, "1M"))

    async def test_load_rejects_misaligned_provider_candle_open(self):
        malformed = dict(SAMPLE[0], open_time=SAMPLE[0]["open_time"] + 1,
                         close_time=SAMPLE[0]["close_time"] + 1)
        with patch.object(api, "_fetch_binance", return_value=[malformed]):
            with self.assertRaises(HTTPException) as ctx:
                await api._load("BTCUSDT", "1h", 5)
        self.assertEqual(ctx.exception.status_code, 502)
        self.assertIn("ambiguous candle sequence", ctx.exception.detail)

    def test_valid_candle_rejects_fractional_and_boolean_timestamps(self):
        fractional = dict(SAMPLE[0], open_time=SAMPLE[0]["open_time"] + 0.5)
        boolean = dict(SAMPLE[0], close_time=True)
        self.assertFalse(api._is_valid_candle(fractional))
        self.assertFalse(api._is_valid_candle(boolean))

if __name__ == "__main__":
    unittest.main()
