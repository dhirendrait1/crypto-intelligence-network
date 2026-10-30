import unittest
from unittest.mock import patch

from scripts.cin_coinpaprika_smoke import (
    MAX_RESPONSE_BYTES,
    TIMEOUT_SECONDS,
    _get_json,
    inspect_tickers,
)


class FakeResponse:
    def __init__(self, payload):
        self.raw = payload if isinstance(payload, bytes) else __import__("json").dumps(payload).encode("utf-8")
        self.requested_size = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size=-1):
        self.requested_size = size
        return self.raw[:size]


class CoinPaprikaSmokeTests(unittest.TestCase):
    def test_valid_public_ticker_contract_passes(self):
        rows = [{
            "id": "btc-bitcoin",
            "name": "Bitcoin",
            "symbol": "BTC",
            "last_updated": "2026-10-30T05:00:00Z",
            "quotes": {"USD": {
                "price": 80000.0,
                "market_cap": 1_500_000_000_000,
                "volume_24h": 20_000_000_000,
            }},
        }]
        report = inspect_tickers(rows)
        self.assertTrue(report["passed"])
        self.assertTrue(report["read_only"])
        self.assertFalse(report["authentication_used"])
        self.assertEqual(report["returned_row_count"], 1)

    def test_missing_bitcoin_or_invalid_metrics_fail_closed(self):
        rows = [{
            "id": "btc-bitcoin", "name": "Bitcoin", "symbol": "BTC",
            "last_updated": "2026-10-30T05:00:00",
            "quotes": {"USD": {"price": "NaN", "market_cap": -1, "volume_24h": None}},
        }]
        report = inspect_tickers(rows)
        self.assertFalse(report["passed"])
        self.assertFalse(report["checks"]["bitcoin_usd_price_positive_finite"])
        self.assertFalse(report["checks"]["bitcoin_market_cap_finite_nonnegative"])
        self.assertFalse(report["checks"]["bitcoin_volume_24h_finite_nonnegative"])
        self.assertFalse(report["checks"]["bitcoin_source_timestamp_timezone_aware"])

    @patch("scripts.cin_coinpaprika_smoke.urllib.request.urlopen")
    def test_get_uses_bounded_read_timeout_and_get_method(self, mocked):
        response = FakeResponse([{"id": "btc-bitcoin"}])
        mocked.return_value = response
        _get_json("https://api.coinpaprika.com/v1/tickers?quotes=USD")
        self.assertEqual(response.requested_size, MAX_RESPONSE_BYTES + 1)
        self.assertEqual(mocked.call_args.kwargs["timeout"], TIMEOUT_SECONDS)
        self.assertEqual(mocked.call_args.args[0].get_method(), "GET")

    @patch("scripts.cin_coinpaprika_smoke.urllib.request.urlopen")
    def test_oversized_response_is_rejected(self, mocked):
        mocked.return_value = FakeResponse(b"x" * (MAX_RESPONSE_BYTES + 1))
        with self.assertRaisesRegex(RuntimeError, "provider_response_too_large"):
            _get_json("https://api.coinpaprika.com/v1/tickers?quotes=USD")


if __name__ == "__main__":
    unittest.main()
