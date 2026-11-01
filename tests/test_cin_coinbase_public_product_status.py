"""Offline public Coinbase product-status regression tests."""
import json
import unittest
from unittest.mock import patch

from cin_coinbase_public_product_status import (
    PUBLIC_PRODUCT_PREFIX, PublicBookError, fetch_coinbase_public_product_status,
)


def product(**changes):
    data = {
        "product_id": "BTC-USD", "base_currency_id": "BTC",
        "quote_currency_id": "USD", "status": "online", "product_type": "SPOT",
        "is_disabled": False, "trading_disabled": False,
        "view_only": False, "auction_mode": False,
    }
    data.update(changes)
    return data


class Response:
    status = 200

    def __init__(self, data, status=200, redirect=False):
        self.body = json.dumps(data).encode("utf-8")
        self.status = status
        self.redirect = redirect

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def geturl(self):
        return "https://untrusted.example/" if self.redirect else PUBLIC_PRODUCT_PREFIX + "BTC-USD"

    def read(self, limit=-1):
        return self.body[:limit] if limit >= 0 else self.body


class CoinbasePublicStatusTests(unittest.TestCase):
    @patch("cin_coinbase_public_product_status.urllib.request.urlopen")
    def test_active_spot_product_is_research_eligible_only(self, opener):
        opener.return_value = Response(product())
        result = fetch_coinbase_public_product_status("BTC-USD")
        self.assertTrue(result["market_available_for_research"])
        self.assertFalse(result["execution_enabled"])
        self.assertFalse(result["authenticated"])
        request = opener.call_args.args[0]
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(request.full_url, PUBLIC_PRODUCT_PREFIX + "BTC-USD")
        self.assertNotIn("authorization", {key.lower() for key in request.headers})

    @patch("cin_coinbase_public_product_status.urllib.request.urlopen")
    def test_non_online_or_non_spot_is_not_research_eligible(self, opener):
        for changes in ({"status": "offline"}, {"status": "delisted"},
                        {"status": "unknown"}, {"product_type": "FUTURE"}):
            with self.subTest(changes=changes):
                opener.return_value = Response(product(**changes))
                result = fetch_coinbase_public_product_status("BTC-USD")
                self.assertFalse(result["market_available_for_research"])

    @patch("cin_coinbase_public_product_status.urllib.request.urlopen")
    def test_disabled_and_restricted_modes_fail_closed(self, opener):
        for field in ("is_disabled", "trading_disabled", "view_only", "auction_mode"):
            opener.return_value = Response(product(**{field: True}))
            with self.subTest(field=field):
                result = fetch_coinbase_public_product_status("BTC-USD")
                self.assertFalse(result["market_available_for_research"])

    @patch("cin_coinbase_public_product_status.urllib.request.urlopen")
    def test_wrong_base_quote_or_product_rejected(self, opener):
        for changes in ({"product_id": "ETH-USD"}, {"base_currency_id": "ETH"},
                        {"quote_currency_id": "USDT"}):
            with self.subTest(changes=changes):
                opener.return_value = Response(product(**changes))
                with self.assertRaises(PublicBookError):
                    fetch_coinbase_public_product_status("BTC-USD")

    @patch("cin_coinbase_public_product_status.urllib.request.urlopen")
    def test_bad_flag_types_or_missing_fields_are_rejected(self, opener):
        for value in (None, 0, "false"):
            with self.subTest(value=value):
                opener.return_value = Response(product(is_disabled=value))
                with self.assertRaisesRegex(PublicBookError, "boolean"):
                    fetch_coinbase_public_product_status("BTC-USD")

    @patch("cin_coinbase_public_product_status.urllib.request.urlopen")
    def test_redirect_and_unexpected_http_status_fail_closed(self, opener):
        for response in (Response(product(), redirect=True), Response(product(), status=503)):
            with self.subTest(response=response):
                opener.return_value = response
                with self.assertRaises(PublicBookError):
                    fetch_coinbase_public_product_status("BTC-USD")

    @patch("cin_coinbase_public_product_status.urllib.request.urlopen")
    def test_malformed_envelope_rejected(self, opener):
        for bad in ([], {}, {"error": "rate limited"}):
            with self.subTest(data=bad):
                opener.return_value = Response(bad)
                with self.assertRaises(PublicBookError):
                    fetch_coinbase_public_product_status("BTC-USD")

    def test_invalid_instrument_rejected_before_network(self):
        with self.assertRaises(ValueError):
            fetch_coinbase_public_product_status("BTC/USD")


if __name__ == "__main__":
    unittest.main()
