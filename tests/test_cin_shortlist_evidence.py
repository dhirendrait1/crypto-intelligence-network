"""Regression tests for source-attributed CIN shortlist evidence."""
import unittest
from datetime import datetime, timedelta, timezone

from cin_shortlist_scoring import WEIGHTS
from cin_shortlist_evidence import assess_evidence

NOW = datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)
GATES = dict.fromkeys(("security_clear", "liquidity_sufficient",
                       "data_reliable", "risk_acceptable"), True)


def factors(age_hours=1):
    return {name: {"score": 80, "source": "offline-test-fixture",
                   "observed_at": (NOW - timedelta(hours=age_hours)).isoformat()}
            for name in WEIGHTS}


class SourceEvidenceTests(unittest.TestCase):
    def test_all_fresh_evidence_is_eligible(self):
        result = assess_evidence("BTC", factors(), GATES, now=NOW)
        self.assertEqual(result["status"], "shortlist_eligible")
        self.assertEqual(result["score"], "80.00")
        self.assertEqual(len(result["factor_sources"]), len(WEIGHTS))
        self.assertEqual(result["source_verification"], "supplied_not_independently_verified")

    def test_stale_factor_makes_candidate_insufficient(self):
        inputs = factors()
        inputs["technical"]["observed_at"] = (NOW - timedelta(hours=25)).isoformat()
        result = assess_evidence("ETH", inputs, GATES, now=NOW)
        self.assertEqual(result["status"], "insufficient_data")
        self.assertIsNone(result["score"])
        self.assertEqual(result["stale_factors"], ["technical"])

    def test_future_timestamp_is_rejected(self):
        inputs = factors()
        inputs["technical"]["observed_at"] = (NOW + timedelta(seconds=1)).isoformat()
        with self.assertRaisesRegex(ValueError, "future"):
            assess_evidence("BTC", inputs, GATES, now=NOW)

    def test_naive_timestamp_and_invalid_source_are_rejected(self):
        inputs = factors()
        inputs["technical"]["observed_at"] = "2026-11-02T11:00:00"
        with self.assertRaisesRegex(ValueError, "timezone"):
            assess_evidence("BTC", inputs, GATES, now=NOW)
        inputs = factors()
        inputs["technical"]["source"] = "bad\nsource"
        with self.assertRaisesRegex(ValueError, "source"):
            assess_evidence("BTC", inputs, GATES, now=NOW)

    def test_unverified_score_does_not_override_failed_gate(self):
        result = assess_evidence("BTC", factors(), dict(GATES, security_clear=False), now=NOW)
        self.assertEqual(result["status"], "rejected")
        self.assertIsNone(result["score"])

    def test_missing_factor_is_not_assumed_neutral(self):
        inputs = factors()
        del inputs["market_regime"]
        result = assess_evidence("BTC", inputs, GATES, now=NOW)
        self.assertEqual(result["status"], "insufficient_data")

    def test_exact_age_boundary_is_fresh(self):
        result = assess_evidence("BTC", factors(age_hours=24), GATES, now=NOW)
        self.assertEqual(result["status"], "shortlist_eligible")

    def test_invalid_factor_shape_and_age_policy_rejected(self):
        inputs = factors()
        inputs["technical"]["extraneous"] = True
        with self.assertRaisesRegex(ValueError, "expected"):
            assess_evidence("BTC", inputs, GATES, now=NOW)
        with self.assertRaisesRegex(ValueError, "max_age"):
            assess_evidence("BTC", factors(), GATES, now=NOW, max_age=timedelta(days=9))


if __name__ == "__main__":
    unittest.main()
