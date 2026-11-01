"""Offline tests for market-data-to-shortlist eligibility bridge."""
import unittest
from datetime import datetime, timedelta, timezone

from cin_shortlist_market_snapshot import assess_market_snapshot

NOW = datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)


def snapshot(**changes):
    row = {
        "id": "bitcoin", "symbol": "BTC", "currency": "USD", "price": 50000.0,
        "last_updated": (NOW - timedelta(minutes=5)).isoformat(),
        "freshness_status": "fresh", "analysis_eligible": True,
        "total_volume_24h": 10000000.0,
    }
    row.update(changes)
    return row


class MarketSnapshotBridgeTests(unittest.TestCase):
    def test_fresh_market_has_insufficient_liquidity_proof(self):
        result = assess_market_snapshot(snapshot(), now=NOW)
        self.assertTrue(result["market_data_fresh"])
        self.assertTrue(result["reported_positive_volume"])
        self.assertIsNone(result["eligibility_evidence"]["liquidity_sufficient"])
        self.assertEqual(result["eligibility_status"], "insufficient_data")

    def test_stale_and_future_market_are_not_reliable(self):
        for updated in (NOW - timedelta(hours=1), NOW + timedelta(seconds=1)):
            with self.subTest(updated=updated):
                result = assess_market_snapshot(
                    snapshot(last_updated=updated.isoformat()), now=NOW)
                self.assertFalse(result["market_data_fresh"])
                self.assertFalse(result["eligibility_evidence"]["data_reliable"])

    def test_provider_flag_cannot_be_overridden(self):
        result = assess_market_snapshot(snapshot(analysis_eligible=False), now=NOW)
        self.assertFalse(result["market_data_fresh"])

    def test_missing_volume_does_not_imply_liquidity(self):
        for volume in (None, 0, float("nan"), True):
            with self.subTest(volume=volume):
                result = assess_market_snapshot(snapshot(total_volume_24h=volume), now=NOW)
                self.assertFalse(result["reported_positive_volume"])
                self.assertIsNone(result["eligibility_evidence"]["liquidity_sufficient"])

    def test_bad_values_fail_closed(self):
        for change in ({"price": float("nan")}, {"price": 0},
                       {"analysis_eligible": 1}, {"symbol": " "},
                       {"last_updated": "2026-11-02T11:00:00"}):
            with self.subTest(change=change):
                with self.assertRaises(ValueError):
                    assess_market_snapshot(snapshot(**change), now=NOW)

    def test_stale_provider_flag_must_be_respected(self):
        result = assess_market_snapshot(snapshot(freshness_status="stale"), now=NOW)
        self.assertFalse(result["market_data_fresh"])


if __name__ == "__main__":
    unittest.main()
