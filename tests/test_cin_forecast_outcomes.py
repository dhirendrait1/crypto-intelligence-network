import unittest

from cin_forecast_outcomes import evaluate_forecast_outcome


def forecast(**overrides):
    value = {
        "forecast_id": "f-1",
        "metric": "BTC-USD",
        "value": 100.0,
        "unit": "USD",
        "target_at": "2026-10-28T12:00:00Z",
    }
    value.update(overrides)
    return value


def actual(**overrides):
    value = {
        "observation_id": "o-1",
        "metric": "BTC-USD",
        "value": 110.0,
        "unit": "USD",
        "observed_at": "2026-10-28T12:01:00Z",
        "source_id": "public-source-a",
    }
    value.update(overrides)
    return value


class ForecastOutcomeTests(unittest.TestCase):
    def test_comparable_horizon_observation_is_evaluated(self):
        result = evaluate_forecast_outcome(forecast(), actual())
        self.assertEqual(result["status"], "evaluated")
        self.assertEqual(result["error"], 10.0)
        self.assertEqual(result["absolute_error"], 10.0)
        self.assertAlmostEqual(result["absolute_percentage_error"], 100 / 11)
        self.assertEqual(result["source_id"], "public-source-a")

    def test_metric_and_unit_mismatch_fail_closed(self):
        self.assertEqual(
            evaluate_forecast_outcome(forecast(), actual(metric="ETH-USD"))["reason"],
            "metric_mismatch",
        )
        self.assertEqual(
            evaluate_forecast_outcome(forecast(), actual(unit="EUR"))["reason"],
            "unit_mismatch",
        )

    def test_observation_before_horizon_not_evaluable(self):
        result = evaluate_forecast_outcome(
            forecast(), actual(observed_at="2026-10-28T11:59:59Z")
        )
        self.assertEqual(result["reason"], "observation_precedes_forecast_horizon")

    def test_zero_actual_has_no_percentage_error(self):
        result = evaluate_forecast_outcome(forecast(value=10), actual(value=0))
        self.assertIsNone(result["absolute_percentage_error"])
        self.assertEqual(result["percentage_error_reason"], "actual_value_is_zero")

    def test_nonfinite_or_boolean_values_rejected(self):
        for value in (float("nan"), float("inf"), True, "100"):
            with self.subTest(value=value):
                self.assertEqual(
                    evaluate_forecast_outcome(forecast(value=value), actual())["reason"],
                    "values_must_be_finite_numbers",
                )

    def test_timezone_naive_timestamps_rejected(self):
        result = evaluate_forecast_outcome(
            forecast(target_at="2026-10-28T12:00:00"), actual()
        )
        self.assertEqual(result["reason"], "timestamps_must_be_timezone_aware")

    def test_missing_provenance_rejected(self):
        result = evaluate_forecast_outcome(forecast(), actual(source_id=""))
        self.assertEqual(result["reason"], "actual_metadata_missing")

    def test_non_object_records_rejected(self):
        self.assertEqual(
            evaluate_forecast_outcome([], actual())["reason"], "records_must_be_objects"
        )


if __name__ == "__main__":
    unittest.main()
