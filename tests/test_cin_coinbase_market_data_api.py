"""Offline API contract tests for the read-only Coinbase candles route."""
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

import cin_coinbase_market_data_api as api


class CoinbaseMarketDataApiTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(api.router)
        self.client = TestClient(app)

    @patch.object(api, "fetch_candles")
    def test_returns_explicit_source_product_and_timestamp_provenance(self, fetch):
        fetch.return_value = [{
            "open_time": 1700000000000,
            "close_time": 1700003599999,
            "open": 100.0, "high": 103.0, "low": 99.0,
            "close": 102.0, "volume": 12.5,
        }]
        response = self.client.get(
            "/coinbase/market-candles",
            params={"product_id": "BTC-USD", "granularity": "1h", "start": 1700000000, "end": 1700003600},
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["mode"], "read_only")
        self.assertEqual(body["source"], "Coinbase Exchange public candles API")
        self.assertEqual(body["product_id"], "BTC-USD")
        self.assertEqual(body["quote_currency"], "USD")
        self.assertEqual(body["count"], 1)
        self.assertIn("retrieved_at", body)
        self.assertIn("open_time_utc", body["data"][0])
        self.assertIn("close_time_utc", body["data"][0])
        self.assertTrue(body["data"][0]["is_closed"])
        fetch.assert_called_once_with("BTC-USD", "1h", 1700000000, 1700003600)

    def test_rejects_missing_time_bounds(self):
        response = self.client.get("/coinbase/market-candles")
        self.assertEqual(response.status_code, 422)

    def test_rejects_unsupported_granularity(self):
        response = self.client.get(
            "/coinbase/market-candles",
            params={"product_id": "BTC-USD", "granularity": "4h", "start": 1700000000, "end": 1700014400},
        )
        self.assertEqual(response.status_code, 400)

    @patch.object(api, "fetch_candles", side_effect=ValueError("Coinbase product must be USD quoted"))
    def test_returns_controlled_validation_error(self, fetch):
        response = self.client.get(
            "/coinbase/market-candles",
            params={"product_id": "BTC-USDT", "granularity": "1h", "start": 1700000000, "end": 1700003600},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("USD quoted", response.json()["detail"])

    @patch.object(api, "fetch_candles", side_effect=RuntimeError("sensitive provider response detail"))
    def test_provider_failure_does_not_leak_provider_exception(self, fetch):
        response = self.client.get(
            "/coinbase/market-candles",
            params={"product_id": "BTC-USD", "granularity": "1h", "start": 1700000000, "end": 1700003600},
        )
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("sensitive", response.text)
        self.assertEqual(
            response.json()["detail"],
            "Coinbase public market-data provider is temporarily unavailable.",
        )


if __name__ == "__main__":
    unittest.main()
