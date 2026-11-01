"""Offline regression tests for declared order-book liquidity diagnostics."""
import unittest
from datetime import datetime, timedelta, timezone

from cin_shortlist_orderbook_liquidity import assess_order_book

NOW = datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)


def book(**kwargs):
    snapshot = {
        "symbol": "BTC-USD",
        "source": "offline-fixture",
        "observed_at": NOW.isoformat(),
        "bids": [["100", "110"], ["99", "1"]],
        "asks": [["101", "110"], ["102", "1"]],
    }
    snapshot.update(kwargs)
    return snapshot


class OrderBookLiquidityTests(unittest.TestCase):
    def test_valid_evidence_is_not_execution_guarantee(self):
        result = assess_order_book(book(), now=NOW, max_spread_bps="101")
        self.assertTrue(result["liquidity_sufficient"])
        self.assertEqual(result["bid_depth_quote"], "11099")
        self.assertEqual(result["ask_depth_quote"], "11212")
        self.assertEqual(result["source_verification"], "supplied_not_independently_verified")

    def test_default_spread_limit_rejects_wide_market(self):
        result = assess_order_book(book(), now=NOW)
        self.assertFalse(result["liquidity_sufficient"])

    def test_each_side_must_independently_meet_depth(self):
        result = assess_order_book(book(asks=[["101", "1"]]), now=NOW, max_spread_bps="101")
        self.assertFalse(result["liquidity_sufficient"])

    def test_stale_book_cannot_pass(self):
        result = assess_order_book(book(observed_at=(NOW-timedelta(seconds=31)).isoformat()),
                                   now=NOW, max_spread_bps="101")
        self.assertFalse(result["snapshot_fresh"])
        self.assertFalse(result["liquidity_sufficient"])

    def test_future_timestamp_rejected(self):
        with self.assertRaisesRegex(ValueError, "future"):
            assess_order_book(book(observed_at=(NOW+timedelta(seconds=1)).isoformat()), now=NOW)

    def test_wrong_order_and_duplicate_price_rejected(self):
        for bad in ([[["99", "1"], ["100", "2"]], [["100", "1"], ["100", "2"]]]):
            with self.subTest(bad=bad):
                with self.assertRaisesRegex(ValueError, "ordered"):
                    assess_order_book(book(bids=bad), now=NOW)

    def test_crossed_and_locked_book_rejected(self):
        for bid in ("101", "102"):
            with self.subTest(bid=bid):
                with self.assertRaisesRegex(ValueError, "crossed or locked"):
                    assess_order_book(book(bids=[[bid, "110"]]), now=NOW)

    def test_malformed_levels_and_nonfinite_numbers_rejected(self):
        for bids in ([], [["100"]], [[True, "2"]], [["NaN", "1"]],
                     [["100", "-1"]], [["100", "0"]], [["inf", "1"]]):
            with self.subTest(bids=bids):
                with self.assertRaises(ValueError):
                    assess_order_book(book(bids=bids), now=NOW)

    def test_naive_time_and_untrusted_source_rejected(self):
        with self.assertRaisesRegex(ValueError, "timezone"):
            assess_order_book(book(observed_at="2026-11-02T12:00:00"), now=NOW)
        with self.assertRaisesRegex(ValueError, "source"):
            assess_order_book(book(source="source\nspoof"), now=NOW)

    def test_invalid_thresholds_rejected(self):
        for value in (True, 0, "NaN", "-2"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    assess_order_book(book(), now=NOW, min_depth_quote_each_side=value)


if __name__ == "__main__":
    unittest.main()
