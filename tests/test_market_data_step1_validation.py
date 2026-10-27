import asyncio
import json
import unittest
import urllib.error
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from market_data_step1 import _fetch_market_data, get_public_market_data


class FakeResponse:
    status = 200

    def __init__(self, payload, status=200):
        self.payload = payload
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, *args):
        return json.dumps(self.payload, allow_nan=True).encode("utf-8")


def row(**overrides):
    value = {
        "id": "bitcoin",
        "symbol": "btc",
        "name": "Bitcoin",
        "current_price": 100.0,
        "market_cap": 1000,
        "total_volume": 100,
        "price_change_percentage_24h": 1.5,
        "last_updated": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    value.update(overrides)
    return value


class MarketDataStep1ValidationTests(unittest.TestCase):
    @patch("market_data_step1.urllib.request.urlopen")
    def test_valid_row_includes_freshness_metadata(self, mocked):
        mocked.return_value = FakeResponse([row()])
        result = _fetch_market_data(["bitcoin"], "usd")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["freshness_status"], "fresh")
        self.assertTrue(result[0]["analysis_eligible"])
        self.assertIsInstance(result[0]["freshness_age_seconds"], int)
        self.assertEqual(result[0]["data_quality_warnings"], [])

    @patch("market_data_step1.urllib.request.urlopen")
    def test_non_finite_or_negative_prices_are_excluded(self, mocked):
        mocked.return_value = FakeResponse([
            row(current_price=float("nan")),
            row(id="negative", current_price=-1),
            row(id="infinite", current_price=float("inf")),
        ])
        self.assertEqual(_fetch_market_data(["bitcoin"], "usd"), [])

    @patch("market_data_step1.urllib.request.urlopen")
    def test_numeric_fields_are_normalized_to_floats(self, mocked):
        mocked.return_value = FakeResponse([row(
            current_price=100, market_cap=1000, total_volume=50,
            price_change_percentage_24h=2,
        )])
        result = _fetch_market_data(["bitcoin"], "usd")[0]
        for field in ("price", "market_cap", "total_volume_24h", "price_change_percentage_24h"):
            self.assertIsInstance(result[field], float)

    @patch("market_data_step1.urllib.request.urlopen")
    def test_zero_and_missing_liquidity_metrics_are_not_overstated(self, mocked):
        mocked.return_value = FakeResponse([row(market_cap=0, total_volume=0)])
        zero = _fetch_market_data(["bitcoin"], "usd")[0]
        self.assertEqual(zero["market_cap_status"], "zero")
        self.assertEqual(zero["volume_24h_status"], "zero")
        self.assertIn("zero_market_cap_not_liquidity_evidence", zero["data_quality_warnings"])
        self.assertIn("zero_volume_not_liquidity_evidence", zero["data_quality_warnings"])

        mocked.return_value = FakeResponse([row(market_cap=None, total_volume=None)])
        missing = _fetch_market_data(["bitcoin"], "usd")[0]
        self.assertEqual(missing["market_cap_status"], "missing")
        self.assertEqual(missing["volume_24h_status"], "missing")
        self.assertIn("market_cap_unavailable", missing["data_quality_warnings"])
        self.assertIn("volume_24h_unavailable", missing["data_quality_warnings"])

    @patch("market_data_step1.urllib.request.urlopen")
    def test_invalid_optional_metrics_are_null_and_warned(self, mocked):
        mocked.return_value = FakeResponse([row(
            market_cap=-1,
            total_volume=float("inf"),
            price_change_percentage_24h=float("nan"),
        )])
        result = _fetch_market_data(["bitcoin"], "usd")[0]
        self.assertIsNone(result["market_cap"])
        self.assertIsNone(result["total_volume_24h"])
        self.assertIsNone(result["price_change_percentage_24h"])
        self.assertIn("invalid_market_cap_omitted", result["data_quality_warnings"])
        self.assertIn("invalid_total_volume_omitted", result["data_quality_warnings"])
        self.assertIn("invalid_price_change_percentage_omitted", result["data_quality_warnings"])

    @patch("market_data_step1.urllib.request.urlopen")
    def test_old_provider_timestamp_is_stale(self, mocked):
        old = (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat()
        mocked.return_value = FakeResponse([row(last_updated=old)])
        result = _fetch_market_data(["bitcoin"], "usd")[0]
        self.assertEqual(result["freshness_status"], "stale")
        self.assertIn("market_data_older_than_15_minutes", result["data_quality_warnings"])

    @patch("market_data_step1.urllib.request.urlopen")
    def test_fractionally_over_15_minutes_is_stale(self, mocked):
        # More than 15 minutes old by a fraction of a second must not become
        # fresh merely because the reported integer age is truncated to 900.
        old = (datetime.now(timezone.utc) - timedelta(minutes=15, milliseconds=500)).isoformat()
        mocked.return_value = FakeResponse([row(last_updated=old)])
        result = _fetch_market_data(["bitcoin"], "usd")[0]
        self.assertEqual(result["freshness_status"], "stale")
        self.assertEqual(result["freshness_age_seconds"], 900)
        self.assertFalse(result["analysis_eligible"])
        self.assertIn("market_data_older_than_15_minutes", result["data_quality_warnings"])

    @patch("market_data_step1.urllib.request.urlopen")
    def test_missing_or_timezone_naive_timestamp_is_unknown(self, mocked):
        mocked.return_value = FakeResponse([row(last_updated="2026-10-24T00:00:00")])
        result = _fetch_market_data(["bitcoin"], "usd")[0]
        self.assertEqual(result["freshness_status"], "unknown")
        self.assertIn("timezone_missing_from_last_updated", result["data_quality_warnings"])

    @patch("market_data_step1.urllib.request.urlopen")
    def test_future_timestamp_is_unknown_and_warned(self, mocked):
        future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        mocked.return_value = FakeResponse([row(last_updated=future)])
        result = _fetch_market_data(["bitcoin"], "usd")[0]
        self.assertEqual(result["freshness_status"], "unknown")
        self.assertIn("future_last_updated_timestamp", result["data_quality_warnings"])


    @patch("market_data_step1.urllib.request.urlopen")
    def test_unexpected_provider_status_is_controlled_error(self, mocked):
        from market_data_step1 import _fetch_market_data
        mocked.return_value = FakeResponse([], status=503)
        with self.assertRaisesRegex(ValueError, "unexpected HTTP status"):
            _fetch_market_data(["bitcoin"], "usd")


    @patch("market_data_step1.urllib.request.urlopen")
    def test_oversized_provider_response_is_rejected(self, mocked):
        class OversizedResponse(FakeResponse):
            def read(self, size=-1):
                return b"x" * size if size >= 0 else b"x" * 2_000_001

        mocked.return_value = OversizedResponse([])
        with self.assertRaisesRegex(ValueError, "exceeded the configured size limit"):
            _fetch_market_data(["bitcoin"], "usd")

    @patch("market_data_step1.urllib.request.urlopen")
    def test_oversized_integer_price_is_excluded_without_overflow(self, mocked):
        mocked.return_value = FakeResponse([row(current_price=10**400)])
        self.assertEqual(_fetch_market_data(["bitcoin"], "usd"), [])


    @patch("market_data_step1.urllib.request.urlopen")
    def test_unrequested_provider_coin_is_excluded(self, mocked):
        mocked.return_value = FakeResponse([row(id="ethereum")])
        self.assertEqual(_fetch_market_data(["bitcoin"], "usd"), [])

    @patch("market_data_step1.urllib.request.urlopen")
    def test_malformed_name_and_symbol_are_omitted_with_warnings(self, mocked):
        mocked.return_value = FakeResponse([row(name={"unexpected": "object"}, symbol=123)])
        result = _fetch_market_data(["bitcoin"], "usd")[0]
        self.assertIsNone(result["name"])
        self.assertIsNone(result["symbol"])
        self.assertIn("invalid_name_omitted", result["data_quality_warnings"])
        self.assertIn("invalid_symbol_omitted", result["data_quality_warnings"])

    @patch("market_data_step1.urllib.request.urlopen")
    def test_control_characters_in_name_and_symbol_are_omitted(self, mocked):
        mocked.return_value = FakeResponse([row(name="Bit\x00coin", symbol="BT\x7fC")])
        result = _fetch_market_data(["bitcoin"], "usd")[0]
        self.assertIsNone(result["name"])
        self.assertIsNone(result["symbol"])

    @patch("market_data_step1.urllib.request.urlopen")
    def test_stale_and_unknown_rows_are_not_analysis_eligible(self, mocked):
        old = (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat()
        mocked.return_value = FakeResponse([row(last_updated=old)])
        stale = _fetch_market_data(["bitcoin"], "usd")[0]
        self.assertEqual(stale["freshness_status"], "stale")
        self.assertFalse(stale["analysis_eligible"])

        mocked.return_value = FakeResponse([row(last_updated="not-a-timestamp")])
        unknown = _fetch_market_data(["bitcoin"], "usd")[0]
        self.assertEqual(unknown["freshness_status"], "unknown")
        self.assertFalse(unknown["analysis_eligible"])

    @patch("market_data_step1.urllib.request.urlopen")
    def test_zero_price_is_preserved_but_not_analysis_eligible(self, mocked):
        mocked.return_value = FakeResponse([row(current_price=0)])
        result = _fetch_market_data(["bitcoin"], "usd")[0]
        self.assertEqual(result["price"], 0)
        self.assertFalse(result["analysis_eligible"])
        self.assertIn("zero_price_not_suitable_for_analysis", result["data_quality_warnings"])


    @patch("market_data_step1.urllib.request.urlopen")
    def test_unrepresentable_timezone_timestamp_is_unknown(self, mocked):
        mocked.return_value = FakeResponse([row(last_updated="0001-01-01T00:00:00+14:00")])
        result = _fetch_market_data(["bitcoin"], "usd")[0]
        self.assertEqual(result["freshness_status"], "unknown")
        self.assertIsNone(result["freshness_age_seconds"])
        self.assertIn("invalid_last_updated_timestamp", result["data_quality_warnings"])

    @patch("market_data_step1.urllib.request.urlopen")
    def test_duplicate_provider_coin_ids_are_not_counted_twice(self, mocked):
        mocked.return_value = FakeResponse([row(), row(current_price=101.0)])
        result = _fetch_market_data(["bitcoin"], "usd")
        self.assertEqual(len(result), 1)


    def test_endpoint_rejects_malformed_currency_codes(self):
        for currency in ("u", "usd!", "us d", "１２３", "abcdefghijk"):
            with self.subTest(currency=currency):
                with self.assertRaises(Exception) as raised:
                    asyncio.run(get_public_market_data("bitcoin", currency))
                self.assertEqual(getattr(raised.exception, "status_code", None), 400)

    @patch("market_data_step1._fetch_market_data")
    def test_provider_rejected_request_is_reported_as_client_error(self, mocked):
        mocked.side_effect = urllib.error.HTTPError("https://api.coingecko.com", 400, "Bad Request", {}, None)
        with self.assertRaises(Exception) as raised:
            asyncio.run(get_public_market_data("bitcoin", "xyz"))
        self.assertEqual(getattr(raised.exception, "status_code", None), 400)
        self.assertIn("not supported", str(raised.exception.detail))

    @patch("market_data_step1._fetch_market_data")
    def test_endpoint_discloses_partial_market_coverage(self, mocked):
        mocked.return_value = [{
            "id": "bitcoin",
            "symbol": "BTC",
            "name": "Bitcoin",
            "currency": "USD",
            "price": 100.0,
            "market_cap": 1000,
            "total_volume_24h": 100,
            "price_change_percentage_24h": 1.5,
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "freshness_status": "fresh",
            "freshness_age_seconds": 0,
            "data_quality_warnings": [],
        }]
        result = asyncio.run(get_public_market_data("bitcoin,ethereum", "usd"))
        self.assertEqual(result["requested_count"], 2)
        self.assertEqual(result["count"], 1)
        self.assertTrue(result["partial_result"])
        self.assertEqual(result["missing_coins"], ["ethereum"])

    @patch("market_data_step1._fetch_market_data")
    def test_endpoint_deduplicates_requested_coin_ids(self, mocked):
        mocked.return_value = [{
            "id": "bitcoin",
            "symbol": "BTC",
            "name": "Bitcoin",
            "currency": "USD",
            "price": 100.0,
            "market_cap": 1000,
            "total_volume_24h": 100,
            "price_change_percentage_24h": 1.5,
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "freshness_status": "fresh",
            "freshness_age_seconds": 0,
            "data_quality_warnings": [],
        }]
        result = asyncio.run(get_public_market_data("bitcoin,bitcoin", "usd"))
        self.assertEqual(result["requested_count"], 1)
        self.assertFalse(result["partial_result"])
        self.assertEqual(result["missing_coins"], [])


    @patch("market_data_step1._fetch_market_data", side_effect=AttributeError("unexpected provider shape"))
    def test_unexpected_provider_shape_is_sanitized(self, mocked):
        with self.assertRaises(Exception) as raised:
            asyncio.run(get_public_market_data("bitcoin", "usd"))
        self.assertEqual(getattr(raised.exception, "status_code", None), 502)
        self.assertEqual(
            raised.exception.detail,
            "Market-data provider returned an unexpected response.",
        )
        self.assertNotIn("unexpected provider shape", raised.exception.detail)
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


if __name__ == "__main__":
    unittest.main()
