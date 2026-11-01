"""Offline status-prefight integration tests. No network calls."""
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from cin_coinbase_status_shortlist_pipeline import research_liquidity_with_market_status

NOW = datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)


def market():
    return {
        "id": "bitcoin", "symbol": "BTC", "currency": "USD", "price": 100.5,
        "last_updated": (NOW - timedelta(minutes=1)).isoformat(),
        "freshness_status": "fresh", "analysis_eligible": True,
        "total_volume_24h": 1000000,
    }


def details(**changes):
    data = {
        "provider": "coinbase", "product_id": "BTC-USD",
        "market_available_for_research": True, "status": "online",
        "product_type": "SPOT", "execution_enabled": False,
    }
    data.update(changes)
    return data


class CoinbaseStatusPipelineTests(unittest.TestCase):
    @patch("cin_coinbase_status_shortlist_pipeline.evaluate_coinbase_liquidity")
    @patch("cin_coinbase_status_shortlist_pipeline.fetch_coinbase_public_product_status")
    def test_active_spot_market_reaches_existing_research_pipeline(self, product, book):
        product.return_value = details()
        book.return_value = {"eligibility_status": "insufficient_data",
                             "eligibility_evidence": {"liquidity_sufficient": None},
                             "execution_enabled": False}
        result = research_liquidity_with_market_status(market(), now=NOW)
        product.assert_called_once_with("BTC-USD")
        book.assert_called_once_with(market(), now=NOW)
        self.assertTrue(result["book_requested"])
        self.assertEqual(result["eligibility_status"], "insufficient_data")
        self.assertIsNone(result["eligibility_evidence"]["liquidity_sufficient"])

    @patch("cin_coinbase_status_shortlist_pipeline.evaluate_coinbase_liquidity")
    @patch("cin_coinbase_status_shortlist_pipeline.fetch_coinbase_public_product_status")
    def test_offline_product_short_circuits_orderbook(self, product, book):
        product.return_value = details(status="offline", market_available_for_research=False)
        result = research_liquidity_with_market_status(market(), now=NOW)
        self.assertEqual(result["status"], "rejected")
        self.assertFalse(result["book_requested"])
        book.assert_not_called()

    @patch("cin_coinbase_status_shortlist_pipeline.evaluate_coinbase_liquidity")
    @patch("cin_coinbase_status_shortlist_pipeline.fetch_coinbase_public_product_status")
    def test_product_identity_tampering_rejected(self, product, book):
        product.return_value = details(product_id="ETH-USD")
        with self.assertRaisesRegex(ValueError, "identity mismatch"):
            research_liquidity_with_market_status(market(), now=NOW)
        book.assert_not_called()

    @patch("cin_coinbase_status_shortlist_pipeline.evaluate_coinbase_liquidity")
    @patch("cin_coinbase_status_shortlist_pipeline.fetch_coinbase_public_product_status")
    def test_execution_boundary_tampering_rejected(self, product, book):
        product.return_value = details(execution_enabled=True)
        with self.assertRaisesRegex(ValueError, "read-only boundary"):
            research_liquidity_with_market_status(market(), now=NOW)
        book.assert_not_called()

    @patch("cin_coinbase_status_shortlist_pipeline.evaluate_coinbase_liquidity")
    @patch("cin_coinbase_status_shortlist_pipeline.fetch_coinbase_public_product_status")
    def test_market_validation_precedes_network(self, product, book):
        bad = dict(market(), price=0)
        with self.assertRaises(ValueError):
            research_liquidity_with_market_status(bad, now=NOW)
        product.assert_not_called()
        book.assert_not_called()


if __name__ == "__main__":
    unittest.main()
