import asyncio
import json
import unittest
import urllib.error
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from market_data_step1 import _fetch_market_data, get_public_market_data


class FakeResponse:
    status = 200

    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size=-1):
        return json.dumps(self.payload).encode("utf-8")


class MarketDataStep1ValidationTests(unittest.TestCase):
    def _responses(self, mocked, stats=None, ticker=None):
        mocked.side_effect = [
            FakeResponse(stats if stats is not None else {"last": "100", "open": "90", "volume": "12"}),
            FakeResponse(ticker if ticker is not None else {"time": datetime.now(timezone.utc).isoformat()}),
        ]

    @patch("market_data_step1.urllib.request.urlopen")
    def test_coinbase_usd_product_and_normalized_read_only_row(self, mocked):
        self._responses(mocked)
        rows = _fetch_market_data(["bitcoin"], "usd")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["product_id"], "BTC-USD")
        self.assertEqual(rows[0]["price"], 100.0)
        self.assertAlmostEqual(rows[0]["price_change_percentage_24h"], 100/90*100-100)
        self.assertIsNone(rows[0]["market_cap"])
        self.assertIn("market_cap_unavailable_from_coinbase_exchange", rows[0]["data_quality_warnings"])
        self.assertEqual(mocked.call_count, 2)
        self.assertIn("/products/BTC-USD/stats", mocked.call_args_list[0].args[0].full_url)
        self.assertIn("/products/BTC-USD/ticker", mocked.call_args_list[1].args[0].full_url)
        self.assertEqual(mocked.call_args_list[0].kwargs["timeout"], 12)

    @patch("market_data_step1.urllib.request.urlopen")
    def test_ethereum_maps_to_coinbase_eth_usd(self, mocked):
        self._responses(mocked)
        rows = _fetch_market_data(["ethereum"], "usd")
        self.assertEqual(rows[0]["product_id"], "ETH-USD")

    @patch("market_data_step1.urllib.request.urlopen")
    def test_coinbase_numeric_strings_are_parsed(self, mocked):
        self._responses(mocked, stats={"last": "123.45", "open": "100", "volume": "50.25"})
        result = _fetch_market_data(["bitcoin"], "usd")[0]
        self.assertEqual(result["price"], 123.45)
        self.assertEqual(result["total_volume_24h"], 50.25)
        self.assertAlmostEqual(result["price_change_percentage_24h"], 23.45)

    @patch("market_data_step1.urllib.request.urlopen")
    def test_unsupported_asset_is_not_substituted(self, mocked):
        self.assertEqual(_fetch_market_data(["unknown-token"], "usd"), [])
        mocked.assert_not_called()

    @patch("market_data_step1.urllib.request.urlopen")
    def test_missing_or_invalid_exchange_price_is_excluded(self, mocked):
        self._responses(mocked, stats={"last": "NaN", "open": "90", "volume": "12"})
        self.assertEqual(_fetch_market_data(["bitcoin"], "usd"), [])

    @patch("market_data_step1.urllib.request.urlopen")
    def test_market_data_timestamp_freshness_is_enforced(self, mocked):
        old = (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat()
        self._responses(mocked, ticker={"time": old})
        row = _fetch_market_data(["bitcoin"], "usd")[0]
        self.assertEqual(row["freshness_status"], "stale")
        self.assertFalse(row["analysis_eligible"])

    def test_endpoint_rejects_non_usd_quote(self):
        with self.assertRaises(Exception) as raised:
            asyncio.run(get_public_market_data("bitcoin", "eur"))
        self.assertEqual(getattr(raised.exception, "status_code", None), 400)

    @patch("market_data_step1._fetch_market_data")
    def test_endpoint_discloses_coinbase_source_and_partial_coverage(self, mocked):
        mocked.return_value = [{
            "id": "bitcoin", "symbol": "BTC", "name": "Bitcoin", "currency": "USD",
            "price": 100.0, "market_cap": None, "market_cap_status": "unavailable",
            "total_volume_24h": 12.0, "volume_24h_status": "reported_positive",
            "price_change_percentage_24h": 1.0, "last_updated": datetime.now(timezone.utc).isoformat(),
            "freshness_status": "fresh", "freshness_age_seconds": 0, "analysis_eligible": True,
            "data_quality_warnings": ["market_cap_unavailable_from_coinbase_exchange"],
        }]
        result = asyncio.run(get_public_market_data("bitcoin,unsupported", "usd"))
        self.assertEqual(result["source"], "Coinbase Exchange public API")
        self.assertEqual(result["missing_coins"], ["unsupported"])
        self.assertTrue(result["partial_result"])
        self.assertEqual(result["provider_limitations"][0].startswith("Coinbase Exchange"), True)

    @patch("market_data_step1.urllib.request.urlopen")
    def test_provider_http_error_remains_controlled(self, mocked):
        mocked.side_effect = urllib.error.HTTPError("https://api.exchange.coinbase.com", 503, "Unavailable", {}, None)
        with self.assertRaises(urllib.error.HTTPError):
            _fetch_market_data(["bitcoin"], "usd")


    @patch("market_data_step1.urllib.request.urlopen")
    def test_coinbase_volume_is_explicitly_base_asset_denominated(self, mocked):
        self._responses(mocked, stats={"last": "100", "open": "90", "volume": "12"})
        result = _fetch_market_data(["bitcoin"], "usd")[0]
        self.assertEqual(result["total_volume_24h"], 12.0)
        self.assertEqual(result["total_volume_24h_unit"], "BTC")
        self.assertEqual(result["volume_24h_currency"], "BTC")

    @patch("market_data_step1.urllib.request.urlopen")
    def test_missing_timezone_timestamp_is_unknown(self, mocked):
        self._responses(mocked, ticker={"time": "2026-10-24T00:00:00"})
        result = _fetch_market_data(["bitcoin"], "usd")[0]
        self.assertEqual(result["freshness_status"], "unknown")
        self.assertFalse(result["analysis_eligible"])
        self.assertIn("timezone_missing_from_last_updated", result["data_quality_warnings"])

    @patch("market_data_step1.urllib.request.urlopen")
    def test_future_timestamp_is_unknown(self, mocked):
        future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        self._responses(mocked, ticker={"time": future})
        result = _fetch_market_data(["bitcoin"], "usd")[0]
        self.assertEqual(result["freshness_status"], "unknown")
        self.assertFalse(result["analysis_eligible"])
        self.assertIn("future_last_updated_timestamp", result["data_quality_warnings"])

    @patch("market_data_step1.urllib.request.urlopen")
    def test_oversized_provider_response_is_rejected(self, mocked):
        class OversizedResponse(FakeResponse):
            def read(self, size=-1):
                return b"x" * (size if size > 0 else 2_000_001)
        mocked.return_value = OversizedResponse({})
        with self.assertRaisesRegex(ValueError, "exceeded the configured size limit"):
            _fetch_market_data(["bitcoin"], "usd")

    @patch("market_data_step1.urllib.request.urlopen")
    def test_unexpected_provider_http_status_is_rejected(self, mocked):
        class UnavailableResponse(FakeResponse):
            status = 503
        mocked.return_value = UnavailableResponse({})
        with self.assertRaisesRegex(ValueError, "unexpected HTTP status 503"):
            _fetch_market_data(["bitcoin"], "usd")

    @patch("market_data_step1.urllib.request.urlopen")
    def test_zero_base_asset_volume_is_not_liquidity_evidence(self, mocked):
        self._responses(mocked, stats={"last": "100", "open": "90", "volume": "0"})
        result = _fetch_market_data(["bitcoin"], "usd")[0]
        self.assertEqual(result["volume_24h_status"], "zero")
        self.assertIn("zero_volume_not_liquidity_evidence", result["data_quality_warnings"])



    @patch("market_data_step1._fetch_market_data")
    def test_coinbase_http_400_is_reported_as_upstream_error(self, mocked):
        mocked.side_effect = urllib.error.HTTPError(
            "https://api.exchange.coinbase.com", 400, "Bad Request", {}, None
        )
        with self.assertRaises(Exception) as raised:
            asyncio.run(get_public_market_data("bitcoin", "usd"))
        self.assertEqual(getattr(raised.exception, "status_code", None), 502)
        self.assertIn("provider returned HTTP 400", raised.exception.detail)


    @patch("market_data_step1.urllib.request.urlopen")
    def test_negative_price_is_excluded(self, mocked):
        self._responses(mocked, stats={"last": "-1", "open": "90", "volume": "12"})
        self.assertEqual(_fetch_market_data(["bitcoin"], "usd"), [])

    @patch("market_data_step1.urllib.request.urlopen")
    def test_non_finite_price_is_excluded(self, mocked):
        self._responses(mocked, stats={"last": "Infinity", "open": "90", "volume": "12"})
        self.assertEqual(_fetch_market_data(["bitcoin"], "usd"), [])

    @patch("market_data_step1.urllib.request.urlopen")
    def test_invalid_optional_volume_is_null_and_warned(self, mocked):
        self._responses(mocked, stats={"last": "100", "open": "90", "volume": "-2"})
        result = _fetch_market_data(["bitcoin"], "usd")[0]
        self.assertIsNone(result["total_volume_24h"])
        self.assertEqual(result["volume_24h_status"], "missing")
        self.assertIn("invalid_total_volume_omitted", result["data_quality_warnings"])
        self.assertIn("volume_24h_unavailable", result["data_quality_warnings"])

    @patch("market_data_step1.urllib.request.urlopen")
    def test_invalid_open_price_does_not_create_percentage_change(self, mocked):
        self._responses(mocked, stats={"last": "100", "open": "0", "volume": "12"})
        result = _fetch_market_data(["bitcoin"], "usd")[0]
        self.assertIsNone(result["price_change_percentage_24h"])
        self.assertIn("price_change_unavailable", result["data_quality_warnings"])

    @patch("market_data_step1.urllib.request.urlopen")
    def test_missing_timestamp_is_unknown_and_not_analysis_eligible(self, mocked):
        self._responses(mocked, ticker={})
        result = _fetch_market_data(["bitcoin"], "usd")[0]
        self.assertEqual(result["freshness_status"], "unknown")
        self.assertIsNone(result["freshness_age_seconds"])
        self.assertFalse(result["analysis_eligible"])

    @patch("market_data_step1.urllib.request.urlopen")
    def test_malformed_provider_object_is_rejected(self, mocked):
        mocked.side_effect = [FakeResponse([])]
        with self.assertRaisesRegex(ValueError, "response was not an object"):
            _fetch_market_data(["bitcoin"], "usd")

    @patch("market_data_step1.urllib.request.urlopen")
    def test_non_json_provider_response_is_rejected(self, mocked):
        class InvalidJsonResponse(FakeResponse):
            def read(self, size=-1):
                return b"{not-json"
        mocked.return_value = InvalidJsonResponse({})
        with self.assertRaises(json.JSONDecodeError):
            _fetch_market_data(["bitcoin"], "usd")



    def test_endpoint_rejects_malformed_currency_codes(self):
        for currency in ("u", "usd!", "us d", "１２３", "abcdefghijk"):
            with self.subTest(currency=currency):
                with self.assertRaises(Exception) as raised:
                    asyncio.run(get_public_market_data("bitcoin", currency))
                self.assertEqual(getattr(raised.exception, "status_code", None), 400)

    @patch("market_data_step1._fetch_market_data")
    def test_endpoint_deduplicates_requested_asset_ids(self, mocked):
        mocked.return_value = [{
            "id": "bitcoin", "symbol": "BTC", "name": "Bitcoin", "currency": "USD",
            "price": 100.0, "market_cap": None, "market_cap_status": "unavailable",
            "total_volume_24h": 12.0, "volume_24h_status": "reported_positive",
            "price_change_percentage_24h": 1.0, "last_updated": datetime.now(timezone.utc).isoformat(),
            "freshness_status": "fresh", "freshness_age_seconds": 0, "analysis_eligible": True,
            "data_quality_warnings": [],
        }]
        result = asyncio.run(get_public_market_data("bitcoin,bitcoin", "usd"))
        self.assertEqual(result["requested_count"], 1)
        self.assertFalse(result["partial_result"])
        self.assertEqual(result["missing_coins"], [])
        mocked.assert_called_once_with(["bitcoin"], "usd")

    @patch("market_data_step1._fetch_market_data", side_effect=RuntimeError("sensitive provider internals"))
    def test_unexpected_provider_runtime_error_is_sanitized(self, mocked):
        with self.assertRaises(Exception) as raised:
            asyncio.run(get_public_market_data("bitcoin", "usd"))
        self.assertEqual(getattr(raised.exception, "status_code", None), 502)
        self.assertEqual(
            raised.exception.detail,
            "Market-data provider returned an unexpected response.",
        )
        self.assertNotIn("sensitive provider internals", raised.exception.detail)
        mocked.assert_called_once_with(["bitcoin"], "usd")

    @patch("market_data_step1.urllib.request.urlopen")
    def test_zero_price_is_preserved_but_not_analysis_eligible(self, mocked):
        self._responses(mocked, stats={"last": "0", "open": "90", "volume": "12"})
        result = _fetch_market_data(["bitcoin"], "usd")[0]
        self.assertEqual(result["price"], 0)
        self.assertFalse(result["analysis_eligible"])
        self.assertIn("zero_price_not_suitable_for_analysis", result["data_quality_warnings"])


if __name__ == "__main__":
    unittest.main()
