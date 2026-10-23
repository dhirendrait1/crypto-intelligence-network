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


if __name__ == "__main__":
    unittest.main()
