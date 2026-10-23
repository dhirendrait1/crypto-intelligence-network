"""Focused offline tests for CIN coin screening; no live provider calls."""
import importlib.util
import pathlib
import unittest

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "coin_screening_step2.py"
SPEC = importlib.util.spec_from_file_location("coin_screening_step2", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class AssetClassificationTests(unittest.TestCase):
    def test_known_stablecoin_symbol_is_classified(self):
        kind, note = MODULE._asset_type({"symbol": "USDC", "name": "USD Coin", "id": "usd-coin"})
        self.assertEqual(kind, "stablecoin")
        self.assertTrue(note)

    def test_wrapped_asset_is_classified(self):
        kind, _ = MODULE._asset_type({"symbol": "WBTC", "name": "Wrapped Bitcoin", "id": "wrapped-bitcoin"})
        self.assertEqual(kind, "wrapped_or_staked")

    def test_unknown_asset_defaults_to_other_crypto(self):
        kind, _ = MODULE._asset_type({"symbol": "ABC", "name": "Example Protocol", "id": "example-protocol"})
        self.assertEqual(kind, "other_crypto")


class ScoreTests(unittest.TestCase):
    def test_score_is_bounded_and_includes_caveats(self):
        result = MODULE._score({
            "id": "example", "symbol": "ABC", "name": "Example",
            "current_price": 1.0, "market_cap": 500_000_000,
            "total_volume": 20_000_000, "fully_diluted_valuation": 600_000_000,
            "circulating_supply": 80_000_000, "total_supply": 100_000_000,
            "price_change_percentage_24h": 2.0, "last_updated": "2026-01-01T00:00:00Z",
        })
        self.assertGreaterEqual(result["screen_score"], 0)
        self.assertLessEqual(result["screen_score"], result["max_score"])
        self.assertEqual(result["asset_type"], "other_crypto")
        self.assertIn("warnings", result)
        self.assertIn("reasons", result)


if __name__ == "__main__":
    unittest.main()
