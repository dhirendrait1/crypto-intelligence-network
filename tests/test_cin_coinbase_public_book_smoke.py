"""Offline smoke-probe tests; all public provider access is mocked."""
import contextlib
import io
import json
import unittest
from unittest.mock import patch

from cin_coinbase_public_book_smoke import probe, run
from cin_coinbase_public_orderbook import PublicBookError


def good_result(fresh=True):
    return {
        "provider": "coinbase",
        "product_id": "BTC-USD",
        "request_method": "GET",
        "execution_enabled": False,
        "authenticated": False,
        "diagnostics": {"snapshot_fresh": fresh, "age_seconds": 2},
        "snapshot": {"bids": [["100", "1"]], "asks": [["101", "1"]]},
    }


class CoinbaseSmokeTests(unittest.TestCase):
    @patch("cin_coinbase_public_book_smoke.fetch_coinbase_public_book")
    def test_fresh_success_has_no_orderbook_prices(self, fetch):
        fetch.return_value = good_result()
        output = probe("BTC-USD")
        self.assertEqual(output["status"], "pass")
        self.assertEqual(output["level_counts"], {"bids": 1, "asks": 1})
        self.assertNotIn("100", json.dumps(output))
        self.assertFalse(output["production_activated"])
        fetch.assert_called_once_with("BTC-USD")

    @patch("cin_coinbase_public_book_smoke.fetch_coinbase_public_book")
    def test_stale_snapshot_is_not_success(self, fetch):
        fetch.return_value = good_result(fresh=False)
        self.assertEqual(probe("BTC-USD")["status"], "stale_snapshot")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = run(["--product", "BTC-USD"])
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(out.getvalue())["status"], "stale_snapshot")

    @patch("cin_coinbase_public_book_smoke.fetch_coinbase_public_book")
    def test_invalid_provider_identity_rejected(self, fetch):
        for field, value in (("provider", "example"), ("request_method", "POST"),
                             ("authenticated", True), ("execution_enabled", True),
                             ("product_id", "ETH-USD")):
            with self.subTest(field=field):
                fetch.return_value = dict(good_result(), **{field: value})
                with self.assertRaisesRegex(PublicBookError, "read-only boundary"):
                    probe("BTC-USD")

    @patch("cin_coinbase_public_book_smoke.fetch_coinbase_public_book")
    def test_provider_failure_is_redacted_and_returns_nonzero(self, fetch):
        fetch.side_effect = PublicBookError("sensitive provider response must stay private")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = run(["--product", "BTC-USD"])
        self.assertEqual(code, 2)
        response = json.loads(out.getvalue())
        self.assertEqual(response["category"], "provider_or_contract_error")
        self.assertNotIn("sensitive", out.getvalue())

    @patch("cin_coinbase_public_book_smoke.fetch_coinbase_public_book")
    def test_transport_failure_classified_without_trace(self, fetch):
        fetch.side_effect = OSError("private runner details")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = run(["--product", "BTC-USD"])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(out.getvalue())["category"], "transport_error")
        self.assertNotIn("private", out.getvalue())

    @patch("cin_coinbase_public_book_smoke.fetch_coinbase_public_book")
    def test_invalid_product_rejected_before_provider(self, fetch):
        with self.assertRaises(ValueError):
            probe("BTC-USDT")
        fetch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
