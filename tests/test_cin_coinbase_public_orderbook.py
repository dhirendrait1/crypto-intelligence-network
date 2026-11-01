"""Offline Coinbase Advanced public book transport/contract regression tests."""
import json
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from cin_coinbase_public_orderbook import (
    PUBLIC_BOOK_URL, PublicBookError, fetch_coinbase_public_book,
)

NOW = datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)


def payload(**overrides):
    row = {
        "product_id": "BTC-USD",
        "bids": [{"price": "100", "size": "200"}],
        "asks": [{"price": "101", "size": "200"}],
        "time": (NOW - timedelta(seconds=2)).isoformat(),
    }
    row.update(overrides)
    return {"pricebook": row}


class FakeResponse:
    status = 200

    def __init__(self, data, *, status=200, redirected=False):
        self.data = json.dumps(data).encode("utf-8")
        self.status = status
        self.redirected = redirected

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def geturl(self):
        url = PUBLIC_BOOK_URL + "?product_id=BTC-USD&limit=50"
        return "https://wrong.example/book" if self.redirected else url

    def read(self, amount=-1):
        return self.data if amount < 0 else self.data[:amount]


class CoinbasePublicBookTests(unittest.TestCase):
    @patch("cin_coinbase_public_orderbook.urllib.request.urlopen")
    def test_valid_public_get_is_read_only(self, opener):
        opener.return_value = FakeResponse(payload())
        result = fetch_coinbase_public_book("BTC-USD", now=NOW)
        request = opener.call_args.args[0]
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(request.full_url, PUBLIC_BOOK_URL + "?product_id=BTC-USD&limit=50")
        self.assertNotIn("authorization", {key.lower() for key in request.headers})
        self.assertFalse(result["execution_enabled"])
        self.assertEqual(result["product_id"], "BTC-USD")
        self.assertTrue(result["diagnostics"]["snapshot_fresh"])
        self.assertEqual(result["snapshot"]["bids"], [["100", "200"]])

    @patch("cin_coinbase_public_orderbook.urllib.request.urlopen")
    def test_wrong_product_rejected(self, opener):
        opener.return_value = FakeResponse(payload(product_id="ETH-USD"))
        with self.assertRaisesRegex(PublicBookError, "identity mismatch"):
            fetch_coinbase_public_book("BTC-USD", now=NOW)

    @patch("cin_coinbase_public_orderbook.urllib.request.urlopen")
    def test_redirect_and_status_rejected(self, opener):
        for response in (FakeResponse(payload(), redirected=True),
                         FakeResponse(payload(), status=503)):
            opener.return_value = response
            with self.assertRaises(PublicBookError):
                fetch_coinbase_public_book("BTC-USD", now=NOW)

    @patch("cin_coinbase_public_orderbook.urllib.request.urlopen")
    def test_malformed_pricebook_rejected(self, opener):
        bad = [
            {"wrong": {}}, {"pricebook": []},
            payload(bids=[]),
            payload(bids=[{"price": 100, "size": "200"}]),
            payload(bids=[{"price": "100", "size": "200", "num_orders": 1}]),
            payload(bids=[{"price": "102", "size": "200"}]),
        ]
        for body in bad:
            with self.subTest(body=body):
                opener.return_value = FakeResponse(body)
                with self.assertRaises(PublicBookError):
                    fetch_coinbase_public_book("BTC-USD", now=NOW)

    @patch("cin_coinbase_public_orderbook.urllib.request.urlopen")
    def test_stale_book_cannot_pass_depth_gate(self, opener):
        opener.return_value = FakeResponse(
            payload(time=(NOW - timedelta(minutes=2)).isoformat()))
        result = fetch_coinbase_public_book("BTC-USD", now=NOW)
        self.assertFalse(result["diagnostics"]["liquidity_sufficient"])

    def test_bad_product_id_rejected_before_network(self):
        for symbol in ("BTC/USD", "btc-usd", "../BTC-USD", " BTC-USD", "A-USD"):
            with self.subTest(symbol=symbol):
                with self.assertRaises(ValueError):
                    fetch_coinbase_public_book(symbol, now=NOW)


if __name__ == "__main__":
    unittest.main()
