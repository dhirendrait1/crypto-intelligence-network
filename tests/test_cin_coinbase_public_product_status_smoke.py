"""Offline tests for the public Coinbase product-status smoke probe."""
import contextlib
import io
import json
import unittest
from unittest.mock import patch

from cin_coinbase_public_product_status_smoke import main, probe


def valid(**kwargs):
    record = {
        "provider": "coinbase", "product_id": "BTC-USD",
        "request_method": "GET", "authenticated": False,
        "execution_enabled": False, "market_available_for_research": True,
        "status": "online", "product_type": "SPOT",
        "flags": {
            "is_disabled": False, "trading_disabled": False,
            "view_only": False, "auction_mode": False,
        },
    }
    record.update(kwargs)
    return record


class ProductStatusSmokeTests(unittest.TestCase):
    @patch("cin_coinbase_public_product_status_smoke.fetch_coinbase_public_product_status")
    def test_valid_status(self, fetch):
        fetch.return_value = valid()
        self.assertEqual(probe("BTC-USD")["status"], "pass")
        fetch.assert_called_once_with("BTC-USD")

    @patch("cin_coinbase_public_product_status_smoke.fetch_coinbase_public_product_status")
    def test_offline_is_nonzero(self, fetch):
        fetch.return_value = valid(status="offline", market_available_for_research=False)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main([])
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(out.getvalue())["status"], "not_eligible")

    @patch("cin_coinbase_public_product_status_smoke.fetch_coinbase_public_product_status")
    def test_provider_and_execution_tampering_fail(self, fetch):
        for field, value in (
            ("provider", "other"), ("product_id", "ETH-USD"),
            ("request_method", "POST"), ("authenticated", True),
            ("execution_enabled", True),
        ):
            with self.subTest(field=field):
                fetch.return_value = valid(**{field: value})
                with self.assertRaisesRegex(ValueError, "identity"):
                    probe("BTC-USD")

    @patch("cin_coinbase_public_product_status_smoke.fetch_coinbase_public_product_status")
    def test_exception_redacts_provider_response(self, fetch):
        fetch.side_effect = ValueError("secrets or raw response")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main([])
        self.assertEqual(code, 2)
        self.assertNotIn("secrets", out.getvalue())
        self.assertEqual(json.loads(out.getvalue())["status"], "fail")

    @patch("cin_coinbase_public_product_status_smoke.fetch_coinbase_public_product_status")
    def test_invalid_product_never_calls_provider(self, fetch):
        with self.assertRaises(ValueError):
            probe("BTC-USDT")
        fetch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
