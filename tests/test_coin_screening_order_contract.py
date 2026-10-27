"""Regression tests for CIN screening output ordering and rank semantics."""
import asyncio
import importlib.util
import pathlib
import unittest
from unittest.mock import patch

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "coin_screening_step2.py"
SPEC = importlib.util.spec_from_file_location("coin_screening_step2_order_contract", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ScreeningOutputOrderContractTests(unittest.TestCase):
    def test_final_output_is_score_first_not_market_cap_rank(self):
        rows = [
            {"id": "large-cap", "symbol": "LGC", "name": "Large Cap", "market_cap": 900},
            {"id": "high-score", "symbol": "HSC", "name": "High Score", "market_cap": 100},
            {"id": "mid-score", "symbol": "MSC", "name": "Mid Score", "market_cap": 500},
        ]
        scores = {
            "large-cap": {"id": "large-cap", "symbol": "LGC", "name": "Large Cap", "market_cap": 900, "screen_score": 20, "asset_type": "other_crypto", "growth_candidate_eligible": True, "analysis_eligible": True, "warnings": [], "screen_band": "watch"},
            "high-score": {"id": "high-score", "symbol": "HSC", "name": "High Score", "market_cap": 100, "screen_score": 90, "asset_type": "other_crypto", "growth_candidate_eligible": True, "analysis_eligible": True, "warnings": [], "screen_band": "strong"},
            "mid-score": {"id": "mid-score", "symbol": "MSC", "name": "Mid Score", "market_cap": 500, "screen_score": 50, "asset_type": "other_crypto", "growth_candidate_eligible": True, "analysis_eligible": True, "warnings": [], "screen_band": "watch"},
        }
        with patch.object(MODULE, "_fetch_markets", return_value=(rows, "live", 0, None)), patch.object(MODULE, "_score", side_effect=lambda row: dict(scores[row["id"]])):
            response = asyncio.run(MODULE.coin_screening(vs_currency="usd", per_page=3, min_score=0, asset_type="all"))

        self.assertEqual([item["id"] for item in response["data"]], ["high-score", "mid-score", "large-cap"])
        self.assertEqual([item["screen_score"] for item in response["data"]], [90, 50, 20])
        # Response order is a heuristic research score, not a market-cap rank.
        self.assertGreater(response["data"][0]["market_cap"], response["data"][1]["market_cap"])
        self.assertNotIn("market_cap_rank", response["data"][0])

    def test_missing_market_cap_stays_null_and_is_not_given_a_rank(self):
        rows = [
            {"id": "missing-cap", "symbol": "MSC", "name": "Missing Cap", "market_cap": None},
            {"id": "known-cap", "symbol": "KNC", "name": "Known Cap", "market_cap": 100},
        ]
        scores = {
            "missing-cap": {"id": "missing-cap", "symbol": "MSC", "name": "Missing Cap", "market_cap": None, "screen_score": 80, "asset_type": "other_crypto", "growth_candidate_eligible": True, "analysis_eligible": True, "warnings": [], "screen_band": "watch"},
            "known-cap": {"id": "known-cap", "symbol": "KNC", "name": "Known Cap", "market_cap": 100, "screen_score": 70, "asset_type": "other_crypto", "growth_candidate_eligible": True, "analysis_eligible": True, "warnings": [], "screen_band": "watch"},
        }
        with patch.object(MODULE, "_fetch_markets", return_value=(rows, "live", 0, None)), patch.object(MODULE, "_score", side_effect=lambda row: dict(scores[row["id"]])):
            response = asyncio.run(MODULE.coin_screening(vs_currency="usd", per_page=2, min_score=0, asset_type="all"))

        self.assertEqual([item["id"] for item in response["data"]], ["missing-cap", "known-cap"])
        self.assertIsNone(response["data"][0]["market_cap"])
        self.assertNotIn("market_cap_rank", response["data"][0])
        self.assertEqual(response["data"][1]["market_cap"], 100)
