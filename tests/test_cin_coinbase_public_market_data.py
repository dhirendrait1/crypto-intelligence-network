"""Offline contract and safety tests for the Coinbase public candle adapter."""
import unittest
from unittest.mock import patch
from urllib.parse import urlparse, parse_qs

import cin_coinbase_public_market_data as coinbase


class CoinbasePublicCandleTests(unittest.TestCase):
    def test_builds_fixed_public_endpoint_with_explicit_usd_product(self):
        payload = [[1700000000, "99", "103", "100", "102", "12.5"]]
        with patch.object(coinbase, "_request_json", return_value=payload) as request:
            rows = coinbase.fetch_candles("BTC-USD", "1h", 1700000000, 1700003600)
        self.assertEqual(len(rows), 1)
        url = request.call_args.args[0]
        parsed = urlparse(url)
        self.assertEqual(parsed.scheme, "https")
        self.assertEqual(parsed.netloc, "api.exchange.coinbase.com")
        self.assertEqual(parsed.path, "/products/BTC-USD/candles")
        self.assertEqual(parse_qs(parsed.query)["granularity"], ["3600"])
        self.assertEqual(rows[0]["open"], 100.0)
        self.assertEqual(rows[0]["high"], 103.0)
        self.assertEqual(rows[0]["low"], 99.0)
        self.assertEqual(rows[0]["close"], 102.0)
        self.assertEqual(rows[0]["volume"], 12.5)
        self.assertEqual(rows[0]["close_time"], 1700003599999)

    def test_rejects_usdt_quote_instead_of_silently_converting_to_usd(self):
        with self.assertRaisesRegex(ValueError, "explicitly USD-quoted"):
            coinbase.fetch_candles("BTC-USDT", "1h", 1700000000, 1700003600)

    def test_rejects_unsupported_granularity(self):
        with self.assertRaisesRegex(ValueError, "granularity"):
            coinbase.fetch_candles("BTC-USD", "4h", 1700000000, 1700014400)

    def test_rejects_window_larger_than_300_candles(self):
        with self.assertRaisesRegex(ValueError, "300-candle"):
            coinbase.fetch_candles("BTC-USD", "1m", 1700000000, 1700018001)

    def test_rejects_boolean_and_invalid_timestamps(self):
        for start, end in ((True, 1700003600), (1700003600, 1700000000), (-1, 1700003600)):
            with self.subTest(start=start, end=end):
                with self.assertRaises(ValueError):
                    coinbase.fetch_candles("BTC-USD", "1h", start, end)

    def test_sorts_rows_and_deduplicates_identical_timestamps(self):
        payload = [
            [1700003600, "99", "103", "101", "102", "12"],
            [1700000000, "98", "102", "100", "101", "10"],
            [1700000000, "98", "102", "100", "101", "10"],
        ]
        with patch.object(coinbase, "_request_json", return_value=payload):
            rows = coinbase.fetch_candles("BTC-USD", "1h", 1700000000, 1700007200)
        self.assertEqual([row["open_time"] for row in rows], [1700000000000, 1700003600000])

    def test_skips_nonfinite_and_impossible_rows(self):
        payload = [
            [1700000000, "99", "103", "100", "102", "12"],
            [1700003600, "99", "98", "100", "102", "12"],
            [1700007200, "99", "103", "100", "NaN", "12"],
            [1700010800, "99", "103", "100", "102", "Infinity"],
            [1700014400, "99", "103", "100", "102", "-1"],
        ]
        with patch.object(coinbase, "_request_json", return_value=payload):
            rows = coinbase.fetch_candles("BTC-USD", "1h", 1700000000, 1700018000)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["open_time"], 1700000000000)

    def test_rejects_more_than_300_provider_rows(self):
        payload = [[1700000000 + i * 60, "99", "103", "100", "102", "1"] for i in range(301)]
        with patch.object(coinbase, "_request_json", return_value=payload):
            with self.assertRaisesRegex(ValueError, "more than 300"):
                coinbase.fetch_candles("BTC-USD", "1m", 1700000000, 1700018000)

    def test_reports_invalid_and_duplicate_provider_rows_without_claiming_coverage(self):
        payload = [
            [1700000000, "99", "103", "100", "102", "12"],
            [1700000000, "99", "103", "100", "102", "12"],
            [1700003600, "99", "98", "100", "102", "12"],
            ["bad", "99", "103", "100", "102", "12"],
        ]
        with patch.object(coinbase, "_request_json", return_value=payload):
            rows, diagnostics = coinbase.fetch_candles_with_diagnostics(
                "BTC-USD", "1h", 1700000000, 1700007200
            )
        self.assertEqual(len(rows), 1)
        self.assertEqual(diagnostics["provider_rows_received"], 4)
        self.assertEqual(diagnostics["provider_rows_invalid"], 2)
        self.assertEqual(diagnostics["provider_rows_duplicate"], 1)
        self.assertEqual(diagnostics["provider_rows_valid_before_deduplication"], 2)
        self.assertEqual(diagnostics["normalized_rows_count"], 1)

    def test_rejects_non_list_provider_payload(self):
        with patch.object(coinbase, "_request_json", return_value={"message": "bad"}):
            with self.assertRaisesRegex(ValueError, "not a list"):
                coinbase.fetch_candles("BTC-USD", "1h", 1700000000, 1700003600)


if __name__ == "__main__":
    unittest.main()
