import json
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from market_data_step1 import _fetch_market_data


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


if __name__ == "__main__":
    unittest.main()
