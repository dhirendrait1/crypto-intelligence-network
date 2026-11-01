"""Offline integration regressions: one Coinbase GET to fail-closed CIN gates."""
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from cin_coinbase_public_orderbook import PUBLIC_BOOK_URL, PublicBookError
from cin_coinbase_shortlist_integration import (
    ShortlistProviderIntegrityError,
    evaluate_coinbase_liquidity,
)

NOW = datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)


def market(**changes):
    row = {
        "id": "bitcoin", "symbol": "BTC", "currency": "USD",
        "price": 100.5,
        "last_updated": (NOW - timedelta(minutes=1)).isoformat(),
        "freshness_status": "fresh", "analysis_eligible": True,
        "total_volume_24h": 25000000,
    }
    row.update(changes)
    return row


def book(**changes):
    row = {
        "provider": "coinbase",
        "product_id": "BTC-USD",
        "endpoint": PUBLIC_BOOK_URL,
        "request_method": "GET",
        "authenticated": False,
        "provenance": "fixed_https_public_endpoint",
        "execution_enabled": False,
        "snapshot": {
            "symbol": "BTC-USD",
            "source": "coinbase-advanced-public-market-product-book",
            "observed_at": (NOW - timedelta(seconds=2)).isoformat(),
            "bids": [["100", "200"]],
            "asks": [["101", "200"]],
        },
    }
    row.update(changes)
    return row


class CoinbaseShortlistIntegrationTests(unittest.TestCase):
    @patch("cin_coinbase_shortlist_integration.fetch_coinbase_public_book")
    def test_public_provider_reconciled_without_fake_eligible_gate(self, fetch):
        fetch.return_value = book()
        result = evaluate_coinbase_liquidity(
            market(), now=NOW, max_spread_bps="101")
        fetch.assert_called_once_with("BTC-USD", now=NOW)
        self.assertTrue(result["reported_orderbook_pass"])
        self.assertEqual(result["eligibility_status"], "insufficient_data")
        self.assertIsNone(result["eligibility_evidence"]["liquidity_sufficient"])
        self.assertIsNone(result["eligibility_evidence"]["security_clear"])
        self.assertFalse(result["execution_enabled"])
        self.assertEqual(result["acquisition"]["market_row_authentication"], "not_verified")

    @patch("cin_coinbase_shortlist_integration.fetch_coinbase_public_book")
    def test_quote_identity_preserved(self, fetch):
        fetch.return_value = book(product_id="BTC-USDT")
        with self.assertRaisesRegex(ShortlistProviderIntegrityError, "mismatch"):
            evaluate_coinbase_liquidity(market(), now=NOW)
        fetch.assert_called_once_with("BTC-USD", now=NOW)

    @patch("cin_coinbase_shortlist_integration.fetch_coinbase_public_book")
    def test_unexpected_provider_provenance_rejected(self, fetch):
        for tampered in (
            {"provider": "not-coinbase"},
            {"endpoint": "https://example.test/book"},
            {"request_method": "POST"},
            {"execution_enabled": True},
            {"authenticated": True},
            {"provenance": "caller-asserted"},
        ):
            with self.subTest(tampered=tampered):
                fetch.return_value = book(**tampered)
                with self.assertRaises(ShortlistProviderIntegrityError):
                    evaluate_coinbase_liquidity(market(), now=NOW)

    @patch("cin_coinbase_shortlist_integration.fetch_coinbase_public_book")
    def test_invalid_market_rejected_before_network(self, fetch):
        for bad in ({"price": 0}, {"symbol": "btc"}, {"currency": "USD/ETH"}):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    evaluate_coinbase_liquidity(market(**bad), now=NOW)
        fetch.assert_not_called()

    @patch("cin_coinbase_shortlist_integration.fetch_coinbase_public_book")
    def test_stale_book_is_negative_gate(self, fetch):
        snap = dict(book()["snapshot"], observed_at=(NOW-timedelta(minutes=2)).isoformat())
        fetch.return_value = book(snapshot=snap)
        result = evaluate_coinbase_liquidity(market(), now=NOW, max_spread_bps="101")
        self.assertEqual(result["eligibility_status"], "rejected")
        self.assertIs(result["eligibility_evidence"]["liquidity_sufficient"], False)

    @patch("cin_coinbase_shortlist_integration.fetch_coinbase_public_book")
    def test_provider_transport_failure_propagates_and_never_fabricates_data(self, fetch):
        fetch.side_effect = PublicBookError("provider unavailable")
        with self.assertRaises(PublicBookError):
            evaluate_coinbase_liquidity(market(), now=NOW)
        fetch.assert_called_once()


if __name__ == "__main__":
    unittest.main()
