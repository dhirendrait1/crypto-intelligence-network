import unittest
from unittest.mock import patch
import cin_public_market_candles_api as api


class KrakenMarketIdentityTests(unittest.TestCase):
    def call(self, symbol, payload):
        with patch.object(api, "_request_json", return_value=payload):
            return api._fetch_kraken(symbol, "1h", 5)

    def rows(self):
        return [[1700000000, "100", "102", "99", "101", "100", "10", 4]]

    def test_accepts_explicit_usdt_pair(self):
        result = self.call("BTCUSDT", {"error": [], "result": {"XBTUSDT": self.rows(), "last": 1}})
        self.assertEqual(result[0]["close"], 101)

    def test_rejects_different_quote(self):
        with self.assertRaisesRegex(ValueError, "market key"):
            self.call("BTCUSDT", {"error": [], "result": {"XXBTZUSD": self.rows(), "last": 1}})

    def test_rejects_unrelated_or_multiple_markets(self):
        for result in ({"ETHUSDT": self.rows(), "last": 1},
                       {"XBTUSDT": self.rows(), "ETHUSDT": self.rows(), "last": 1},
                       {"last": 1}):
            with self.subTest(result=result), self.assertRaisesRegex(ValueError, "market key"):
                self.call("BTCUSDT", {"error": [], "result": result})

    def test_accepts_known_usd_alias(self):
        result = self.call("BTCUSD", {"error": [], "result": {"XXBTZUSD": self.rows(), "last": 1}})
        self.assertEqual(result[0]["close"], 101)

    def test_malformed_error_envelope_never_counts_as_success(self):
        for error in (None, "", [True], [""]):
            with self.subTest(error=error), self.assertRaisesRegex(ValueError, "error field"):
                self.call("BTCUSDT", {"error": error, "result": {"XBTUSDT": self.rows()}})

