import unittest

from cin_alert_rules import evaluate_alert_rule


def rule(**overrides):
    data = {"rule_id": "btc-above-100", "operator": "above", "threshold": 100.0, "unit": "USD", "enabled": True}
    data.update(overrides)
    return data


def observation(**overrides):
    data = {"value": 101.0, "unit": "USD", "freshness_status": "fresh",
            "observation_id": "obs-1", "observed_at": "2026-10-28T00:00:00Z",
            "retrieved_at": "2026-10-28T00:00:01Z", "source_id": "test-source"}
    data.update(overrides)
    return data


class AlertRuleEvaluationTests(unittest.TestCase):
    def test_above_triggers_only_strictly_above_threshold(self):
        self.assertTrue(evaluate_alert_rule(rule(), observation(value=100.01))["triggered"])
        self.assertFalse(evaluate_alert_rule(rule(), observation(value=100.0))["triggered"])

    def test_below_operator(self):
        result = evaluate_alert_rule(rule(operator="below"), observation(value=99.0))
        self.assertTrue(result["triggered"])

    def test_rejects_boolean_nan_and_infinite_values(self):
        for value in (True, float("nan"), float("inf"), float("-inf"), "101"):
            with self.subTest(value=value):
                result = evaluate_alert_rule(rule(), observation(value=value))
                self.assertEqual(result["status"], "ineligible")

    def test_stale_unknown_or_conflicted_observation_is_ineligible(self):
        for obs, reason in (
            (observation(freshness_status="stale"), "observation_not_fresh"),
            (observation(freshness_status="unknown"), "observation_not_fresh"),
            (observation(conflict_status="material_conflict"), "material_source_conflict"),
        ):
            with self.subTest(reason=reason):
                result = evaluate_alert_rule(rule(), obs)
                self.assertEqual(result["status"], "ineligible")
                self.assertEqual(result["reason"], reason)
                self.assertFalse(result["triggered"])

    def test_unit_mismatch_is_ineligible(self):
        result = evaluate_alert_rule(rule(), observation(unit="USDT"))
        self.assertEqual(result["reason"], "unit_mismatch")

    def test_disabled_rule_never_triggers(self):
        result = evaluate_alert_rule(rule(enabled=False), observation())
        self.assertEqual(result["status"], "disabled")
        self.assertFalse(result["triggered"])

    def test_crossing_first_observation_is_baseline(self):
        result = evaluate_alert_rule(rule(operator="crosses_above"), observation(value=101))
        self.assertEqual(result["status"], "baseline")
        self.assertFalse(result["triggered"])

    def test_crossing_requires_cross_from_or_below_to_strictly_above(self):
        r = rule(operator="crosses_above")
        prev = observation(value=100)
        self.assertTrue(evaluate_alert_rule(r, observation(value=100.1), prev)["triggered"])
        self.assertFalse(evaluate_alert_rule(r, observation(value=100), prev)["triggered"])
        self.assertFalse(evaluate_alert_rule(r, observation(value=99.9), prev)["triggered"])

    def test_crossing_below_requires_cross_from_or_above_to_strictly_below(self):
        r = rule(operator="crosses_below")
        prev = observation(value=100)
        self.assertTrue(evaluate_alert_rule(r, observation(value=99.9), prev)["triggered"])
        self.assertFalse(evaluate_alert_rule(r, observation(value=100), prev)["triggered"])

    def test_previous_stale_or_incomparable_sample_cannot_define_crossing(self):
        r = rule(operator="crosses_above")
        self.assertEqual(
            evaluate_alert_rule(r, observation(value=101), observation(value=99, freshness_status="stale"))["status"],
            "baseline",
        )
        self.assertEqual(
            evaluate_alert_rule(r, observation(value=101), observation(value=99, unit="USDT"))["status"],
            "baseline",
        )

    def test_result_carries_observation_provenance(self):
        obs = observation()
        result = evaluate_alert_rule(rule(), obs)
        for key in ("observation_id", "observed_at", "retrieved_at", "source_id"):
            self.assertEqual(result[key], obs[key])


if __name__ == "__main__":
    unittest.main()
