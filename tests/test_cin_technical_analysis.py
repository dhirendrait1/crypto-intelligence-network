"""Offline tests for CIN technical analysis; no external provider calls."""
import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("cin_technical_analysis", ROOT / "cin_technical_analysis.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def candles_from_closes(closes):
    return [{"open": x - 0.2, "high": x + 1, "low": x - 1, "close": x} for x in closes]


class TechnicalAnalysisTests(unittest.TestCase):
    def test_short_input_returns_neutral_scenario_without_targets(self):
        result = module.analyze_ohlc(candles_from_closes([10, 11, 12, 11, 12]))
        self.assertEqual(result["mode"], "read_only")
        self.assertIsNone(result["scenario_targets"]["targets"])
        self.assertIn("not predictions", " ".join(result["limitations"]))

    def test_invalid_ohlc_is_rejected(self):
        bars = candles_from_closes([10, 11, 12, 11, 12])
        bars[0] = {"open": 10, "high": 8, "low": 9, "close": 11}
        with self.assertRaises(ValueError):
            module.analyze_ohlc(bars)

    def test_long_series_computes_indicators(self):
        closes = [100 + i * 0.7 + ((i % 4) - 1.5) * 0.4 for i in range(60)]
        result = module.analyze_ohlc(candles_from_closes(closes))
        self.assertIsNotNone(result["indicators"]["rsi_14"])
        self.assertIsNotNone(result["indicators"]["macd_line"])
        self.assertIsNotNone(result["indicators"]["atr_14"])
        self.assertIn("targets", result["scenario_targets"])

    def test_rejects_more_than_500_candles(self):
        with self.assertRaises(ValueError):
            module.analyze_ohlc(candles_from_closes([100 + i for i in range(501)]))

    def test_volume_metrics_are_reported_when_volume_is_supplied(self):
        bars = candles_from_closes([100 + i for i in range(25)])
        for i, bar in enumerate(bars):
            bar["volume"] = 100.0
        bars[-1]["volume"] = 200.0
        result = module.analyze_ohlc(bars)
        self.assertEqual(result["indicators"]["volume_latest"], 200.0)
        self.assertEqual(result["indicators"]["volume_average_20"], 100.0)
        self.assertEqual(result["indicators"]["relative_volume_20"], 2.0)
        self.assertEqual(result["indicators"]["volume_analysis_status"], "available")

    def test_volume_must_be_present_for_all_candles_or_none(self):
        bars = candles_from_closes([10, 11, 12, 11, 12])
        bars[0]["volume"] = 10
        with self.assertRaisesRegex(ValueError, "every candle"):
            module.analyze_ohlc(bars)

    def test_negative_volume_is_rejected(self):
        bars = candles_from_closes([10, 11, 12, 11, 12])
        for bar in bars:
            bar["volume"] = 10
        bars[-1]["volume"] = -1
        with self.assertRaisesRegex(ValueError, "non-negative"):
            module.analyze_ohlc(bars)


    def test_request_model_rejects_timeframe_whitespace_and_control_characters(self):
        from pydantic import ValidationError
        from cin_technical_analysis_api import TechnicalAnalysisRequest

        valid = {
            "symbol": "BTCUSDT",
            "timeframe": "1h",
            "candles": candles_from_closes([10, 11, 12, 11, 12]),
        }
        self.assertEqual(TechnicalAnalysisRequest.model_validate(valid).timeframe, "1h")
        for timeframe in ("1 h", "1h\\n", "1h\\t", " "):
            with self.subTest(timeframe=repr(timeframe)):
                payload = dict(valid, timeframe=timeframe)
                with self.assertRaises(ValidationError):
                    TechnicalAnalysisRequest.model_validate(payload)

    def test_request_model_rejects_unknown_fields_and_accepts_omitted_timeframe(self):
        from pydantic import ValidationError
        from cin_technical_analysis_api import TechnicalAnalysisRequest

        payload = {
            "symbol": "BTCUSDT",
            "candles": candles_from_closes([10, 11, 12, 11, 12]),
        }
        self.assertEqual(TechnicalAnalysisRequest.model_validate(payload).timeframe, "unspecified")
        with self.assertRaises(ValidationError):
            TechnicalAnalysisRequest.model_validate(dict(payload, order_side="BUY"))


if __name__ == "__main__":
    unittest.main()

    def test_rsi_constant_series_is_neutral(self):
        self.assertEqual(module._rsi([100.0] * 15), 50.0)

    def test_rsi_monotonic_series_reaches_expected_bounds(self):
        self.assertEqual(module._rsi([float(i) for i in range(15)]), 100.0)
        self.assertEqual(module._rsi([float(15 - i) for i in range(15)]), 0.0)

    def test_rsi_requires_more_observations_than_its_period(self):
        self.assertIsNone(module._rsi([float(i) for i in range(14)]))
        self.assertIsNotNone(module._rsi([float(i) for i in range(15)]))

    def test_ema_seed_appears_at_exact_period_boundary(self):
        self.assertEqual(module._ema([1.0] * 11, 12), [None] * 11)
        result = module._ema([1.0] * 12, 12)
        self.assertEqual(result[:11], [None] * 11)
        self.assertEqual(result[11], 1.0)

    def test_atr_requires_period_plus_one_candles(self):
        bars = candles_from_closes([100.0 + i for i in range(15)])
        self.assertIsNone(module._atr(bars[:14]))
        self.assertIsNotNone(module._atr(bars[:15]))

    def test_zero_prior_volume_baseline_does_not_emit_relative_volume(self):
        bars = candles_from_closes([100.0 + i for i in range(25)])
        for bar in bars:
            bar["volume"] = 0.0
        bars[-1]["volume"] = 10.0
        result = module.analyze_ohlc(bars)
        self.assertEqual(result["indicators"]["volume_average_20"], 0.0)
        self.assertIsNone(result["indicators"]["relative_volume_20"])

    def test_macd_signal_line_boundary_is_deterministic(self):
        closes = [100 + i * 0.5 + ((i % 3) - 1) * 0.2 for i in range(34)]
        result = module.analyze_ohlc(candles_from_closes(closes))
        self.assertIsNotNone(result["indicators"]["macd_line"])
        self.assertIsNotNone(result["indicators"]["macd_signal"])
        short = module.analyze_ohlc(candles_from_closes(closes[:-1]))
        self.assertIsNotNone(short["indicators"]["macd_line"])
        self.assertIsNone(short["indicators"]["macd_signal"])
