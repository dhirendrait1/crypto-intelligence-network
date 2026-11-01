"""Offline regression tests for read-only shortlist scoring."""
import unittest
from decimal import Decimal

from cin_shortlist_scoring import WEIGHTS, SCORE_VERSION, assess_candidate, classify

GOOD_GATES = {
    "security_clear": True,
    "liquidity_sufficient": True,
    "data_reliable": True,
    "risk_acceptable": True,
}


class ShortlistScoringTests(unittest.TestCase):
    def test_weights_sum_to_one_hundred(self):
        self.assertEqual(sum(WEIGHTS.values()), 100)

    def test_complete_candidate_is_deterministic(self):
        scores = {name: 80 for name in WEIGHTS}
        actual = assess_candidate("BTC", scores, GOOD_GATES)
        self.assertEqual(actual["score_version"], SCORE_VERSION)
        self.assertEqual(actual["score"], "80.00")
        self.assertEqual(actual["status"], "shortlist_eligible")
        self.assertEqual(actual["classification"], "A")
        self.assertEqual(actual, assess_candidate("BTC", dict(reversed(list(scores.items()))), dict(GOOD_GATES)))

    def test_missing_critical_data_never_receives_estimated_score(self):
        result = assess_candidate("ETH", {"liquidity": 80}, GOOD_GATES)
        self.assertEqual(result["status"], "insufficient_data")
        self.assertIsNone(result["score"])
        self.assertIn("technical", result["missing_dimensions"])

    def test_unknown_eligibility_is_not_assumed_safe(self):
        result = assess_candidate("ETH", dict.fromkeys(WEIGHTS, 90), {"security_clear": True})
        self.assertEqual(result["status"], "insufficient_data")
        self.assertIn("data_reliable", result["missing_gates"])

    def test_failed_gate_overrides_top_score(self):
        result = assess_candidate("ETH", dict.fromkeys(WEIGHTS, 100), dict(GOOD_GATES, security_clear=False))
        self.assertEqual(result["status"], "rejected")
        self.assertIsNone(result["score"])
        self.assertIn("security_clear", result["failed_gates"])

    def test_all_score_bands(self):
        for score, expected in [(0,"F"),(34.99,"F"),(35,"D"),(49.99,"D"),
                                (50,"C"),(64.99,"C"),(65,"B"),(74.99,"B"),
                                (75,"A"),(84.99,"A"),(85,"A+"),(100,"A+")]:
            with self.subTest(score=score):
                result = assess_candidate("BTC", dict.fromkeys(WEIGHTS, score), GOOD_GATES)
                self.assertEqual(result["classification"], expected)
                self.assertEqual(result["classification"], classify(Decimal(str(score))))

    def test_bad_score_values_fail_closed(self):
        for bad in (True, None, [], {}, "nan", "Infinity", -1, 101, "", "junk", float("inf")):
            with self.subTest(bad=repr(bad)):
                with self.assertRaises(ValueError):
                    assess_candidate("BTC", dict.fromkeys(WEIGHTS, 80) | {"technical": bad}, GOOD_GATES)

    def test_unknown_dimensions_or_gates_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown scoring"):
            assess_candidate("BTC", {"made_up": 90}, GOOD_GATES)
        with self.assertRaisesRegex(ValueError, "unknown eligibility"):
            assess_candidate("BTC", dict.fromkeys(WEIGHTS, 80), dict(GOOD_GATES, trading_enabled=False))

    def test_non_boolean_gate_values_rejected(self):
        for bad in (1, 0, "true", None):
            with self.subTest(bad=bad):
                with self.assertRaisesRegex(ValueError, "booleans"):
                    assess_candidate("BTC", dict.fromkeys(WEIGHTS, 80), dict(GOOD_GATES, security_clear=bad))

    def test_no_live_provider_or_order_side_effects(self):
        result = assess_candidate("BTC", dict.fromkeys(WEIGHTS, "70"), GOOD_GATES)
        self.assertEqual(set(result), {
            "symbol", "score_version", "missing_dimensions", "missing_gates",
            "failed_gates", "status", "score", "classification",
        })


if __name__ == "__main__":
    unittest.main()
