import math
import unittest

from cin_forecast_scorecards import build_forecast_scorecard


def row(predicted, actual, **overrides):
    error = actual - predicted
    result = {
        "status": "evaluated",
        "metric": "BTC-USD",
        "unit": "USD",
        "predicted_value": predicted,
        "actual_value": actual,
        "error": error,
        "absolute_error": abs(error),
    }
    result.update(overrides)
    return result


class ForecastScorecardTests(unittest.TestCase):
    def test_computes_descriptive_error_metrics(self):
        result = build_forecast_scorecard([row(100, 110), row(100, 90)])
        self.assertEqual(result["status"], "computed")
        self.assertEqual(result["sample_count"], 2)
        self.assertEqual(result["mean_error"], 0)
        self.assertEqual(result["mean_absolute_error"], 10)
        self.assertAlmostEqual(result["root_mean_squared_error"], 10)
        self.assertAlmostEqual(result["mean_absolute_percentage_error"], (100 / 11 + 100 / 9) / 2)

    def test_recomputes_error_instead_of_trusting_input(self):
        result = build_forecast_scorecard([row(100, 110, error=999, absolute_error=999)])
        self.assertEqual(result["mean_error"], 10)
        self.assertEqual(result["mean_absolute_error"], 10)

    def test_excludes_invalid_and_non_evaluated_rows(self):
        result = build_forecast_scorecard([row(1, 2), {"status": "not_evaluable"}, "bad"])
        self.assertEqual(result["sample_count"], 1)
        self.assertEqual(result["excluded_count"], 2)

    def test_does_not_pool_different_metrics_or_units(self):
        result = build_forecast_scorecard([
            row(100, 110), row(100, 105, metric="ETH-USD"), row(100, 102, unit="EUR")
        ])
        self.assertEqual(result["sample_count"], 1)
        self.assertEqual(result["excluded_count"], 2)

    def test_zero_actual_excluded_only_from_percentage_metric(self):
        result = build_forecast_scorecard([row(1, 0), row(100, 110)])
        self.assertEqual(result["sample_count"], 2)
        self.assertEqual(result["percentage_error_sample_count"], 1)
        self.assertEqual(result["percentage_error_excluded_zero_actual_count"], 1)

    def test_empty_input_reports_insufficient_data(self):
        result = build_forecast_scorecard([])
        self.assertEqual(result["status"], "insufficient_data")
        self.assertEqual(result["sample_count"], 0)

    def test_rejects_non_list(self):
        self.assertEqual(build_forecast_scorecard(None)["status"], "invalid_input")

    def test_non_finite_numbers_are_excluded(self):
        result = build_forecast_scorecard([row(float("nan"), 1), row(1, 2)])
        self.assertEqual(result["sample_count"], 1)
        self.assertEqual(result["excluded_count"], 1)


if __name__ == "__main__":
    unittest.main()
