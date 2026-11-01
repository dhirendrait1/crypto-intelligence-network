"""Offline regression tests for CIN market/Level 2 evidence reconciliation."""
import unittest
from datetime import datetime, timedelta, timezone

from cin_shortlist_liquidity_reconciliation import reconcile_liquidity

NOW = datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)


def market(**changes):
    row = {
        "id": "bitcoin", "symbol": "BTC", "currency": "USD",
        "price": 100.5, "last_updated": (NOW - timedelta(minutes=1)).isoformat(),
        "freshness_status": "fresh", "analysis_eligible": True,
        "total_volume_24h": 2000000,
    }
    return dict(row, **changes)


def book(**changes):
    row = {
        "symbol": "BTC-USD", "source": "offline-source-not-verified",
        "observed_at": (NOW - timedelta(seconds=5)).isoformat(),
        "bids": [["100", "200"]], "asks": [["101", "200"]],
    }
    return dict(row, **changes)


class LiquidityReconciliationTests(unittest.TestCase):
    def test_positive_book_is_not_automatically_trusted(self):
        result = reconcile_liquidity(
            market(), book(), now=NOW, max_spread_bps="101")
        self.assertTrue(result["reported_orderbook_pass"])
        self.assertEqual(result["eligibility_status"], "insufficient_data")
        self.assertIsNone(result["eligibility_evidence"]["liquidity_sufficient"])
        self.assertEqual(result["provider_authentication"], "unverified_caller_supplied")
        self.assertIsNone(result["eligibility_evidence"]["security_clear"])

    def test_wide_book_is_a_negative_signal(self):
        result = reconcile_liquidity(market(), book(), now=NOW)
        self.assertFalse(result["reported_orderbook_pass"])
        self.assertEqual(result["eligibility_status"], "rejected")
        self.assertIs(result["eligibility_evidence"]["liquidity_sufficient"], False)

    def test_stale_book_cannot_qualify(self):
        result = reconcile_liquidity(
            market(), book(observed_at=(NOW - timedelta(minutes=1)).isoformat()),
            now=NOW, max_spread_bps="101")
        self.assertFalse(result["book_snapshot_fresh"])
        self.assertIs(result["eligibility_evidence"]["liquidity_sufficient"], False)

    def test_stale_market_data_cannot_qualify(self):
        row = market(last_updated=(NOW - timedelta(hours=1)).isoformat())
        result = reconcile_liquidity(row, book(), now=NOW, max_spread_bps="101")
        self.assertFalse(result["market_data_fresh"])
        self.assertFalse(result["eligibility_evidence"]["data_reliable"])

    def test_cross_pair_market_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "identity"):
            reconcile_liquidity(market(currency="USDT"), book(),
                                now=NOW, max_spread_bps="101")

    def test_spoofed_source_label_not_proof_of_verification(self):
        result = reconcile_liquidity(
            market(), book(source="official-coinbase-verified"),
            now=NOW, max_spread_bps="101")
        self.assertEqual(result["provider_authentication"], "unverified_caller_supplied")
        self.assertIsNone(result["eligibility_evidence"]["liquidity_sufficient"])

    def test_malformed_order_book_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "crossed"):
            reconcile_liquidity(market(), book(bids=[["102", "100"]]), now=NOW)

    def test_reported_volume_never_grants_positive_gate(self):
        result = reconcile_liquidity(
            market(total_volume_24h=100000000000), book(),
            now=NOW, max_spread_bps="101")
        self.assertIsNone(result["eligibility_evidence"]["liquidity_sufficient"])


if __name__ == "__main__":
    unittest.main()
