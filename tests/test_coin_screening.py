"""Focused offline tests for CIN coin screening; no live provider calls."""
import importlib.util
import pathlib
import unittest
from unittest.mock import patch, MagicMock
import json

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

    def test_gold_backed_tokens_get_commodity_category(self):
        for coin in (
            {"symbol": "XAUT", "name": "Tether Gold", "id": "tether-gold"},
            {"symbol": "PAXG", "name": "PAX Gold", "id": "pax-gold"},
            {"symbol": "GLD", "name": "Example Tokenized Gold", "id": "example-tokenized-gold"},
        ):
            with self.subTest(coin=coin):
                kind, note = MODULE._asset_type(coin)
                self.assertEqual(kind, "commodity_backed")
                self.assertTrue(note)


    def test_commodity_scan_filters_full_provider_list_before_limit(self):
        payload = [
            {"id": "btc-bitcoin", "symbol": "BTC", "name": "Bitcoin", "quotes": {"USD": {"price": 100, "market_cap": 1000, "volume_24h": 10}}},
            {"id": "tether-gold", "symbol": "XAUT", "name": "Tether Gold", "circulating_supply": 10, "total_supply": 10, "quotes": {"USD": {"price": 2000, "market_cap": 900, "volume_24h": 20}}},
            {"id": "pax-gold", "symbol": "PAXG", "name": "PAX Gold", "circulating_supply": 8, "total_supply": 8, "quotes": {"USD": {"price": 2000, "market_cap": 800, "volume_24h": 15}}},
        ]
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps(payload).encode("utf-8")
        with patch.object(MODULE.urllib.request, "urlopen", return_value=response):
            rows, mode, error_code, scanned, matches = MODULE._fetch_commodity_markets("usd", 1)
        self.assertEqual(mode, "live")
        self.assertEqual(error_code, 0)
        self.assertEqual(scanned, 3)
        self.assertEqual(matches, 2)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["symbol"], "XAUT")
        self.assertEqual(rows[0]["_cin_scanned_universe"], 3)


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
        self.assertTrue(result["growth_candidate_eligible"])
        self.assertEqual(result["screen_profile"], "growth_research")

    def test_stablecoin_high_metric_score_is_not_a_growth_candidate(self):
        result = MODULE._score({
            "id": "tether", "symbol": "USDT", "name": "Tether",
            "current_price": 1.0, "market_cap": 500_000_000,
            "total_volume": 20_000_000, "fully_diluted_valuation": 500_000_000,
            "circulating_supply": 500_000_000, "total_supply": 500_000_000,
            "price_change_percentage_24h": 0.1,
        })
        self.assertEqual(result["asset_type"], "stablecoin")
        self.assertFalse(result["growth_candidate_eligible"])
        self.assertEqual(result["screen_profile"], "stablecoin_monitoring")
        self.assertEqual(result["screen_band"], "excluded_non_growth_asset")
        self.assertEqual(result["screen_score"], 100)

    def test_commodity_backed_asset_is_not_a_growth_candidate(self):
        result = MODULE._score({
            "id": "tether-gold", "symbol": "XAUT", "name": "Tether Gold",
            "current_price": 2000.0, "market_cap": 500_000_000,
            "total_volume": 20_000_000, "fully_diluted_valuation": 500_000_000,
            "circulating_supply": 250_000, "total_supply": 250_000,
            "price_change_percentage_24h": 0.1,
        })
        self.assertEqual(result["asset_type"], "commodity_backed")
        self.assertFalse(result["growth_candidate_eligible"])
        self.assertEqual(result["screen_band"], "excluded_non_growth_asset")


class ProviderFallbackMappingTests(unittest.TestCase):
    def test_coinpaprika_fallback_does_not_invent_fdv_from_total_supply(self):
        payload = [
            {
                "id": "unknown-supply-coin", "symbol": "UNK", "name": "Unknown Supply",
                "circulating_supply": 5, "total_supply": 10, "max_supply": None,
                "last_updated": "2026-10-24T00:00:00Z",
                "quotes": {"USD": {"price": 2.0, "market_cap": 10.0, "volume_24h": 3.0, "percent_change_24h": 1.0}},
            },
            {
                "id": "capped-coin", "symbol": "CAP", "name": "Capped Coin",
                "circulating_supply": 5, "total_supply": 8, "max_supply": 10,
                "last_updated": "2026-10-24T00:00:00Z",
                "quotes": {"USD": {"price": 2.0, "market_cap": 10.0, "volume_24h": 3.0, "percent_change_24h": 1.0}},
            },
        ]
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps(payload).encode("utf-8")
        primary_error = MODULE.urllib.error.HTTPError(
            "https://api.coingecko.com/api/v3/coins/markets", 503, "unavailable", {}, None
        )
        with patch.object(MODULE.urllib.request, "urlopen", side_effect=[primary_error, response]):
            rows = MODULE._request_markets("usd", 2)

        self.assertEqual([row["_cin_provider"] for row in rows], ["CoinPaprika", "CoinPaprika"])
        self.assertIsNone(rows[0]["fully_diluted_valuation"])
        self.assertEqual(rows[1]["fully_diluted_valuation"], 20.0)
        self.assertEqual(rows[0]["total_supply"], 10)
        self.assertEqual(rows[0]["last_updated"], "2026-10-24T00:00:00Z")

    def test_coinpaprika_commodity_scan_also_leaves_fdv_unknown_without_max_supply(self):
        payload = [
            {
                "id": "tether-gold", "symbol": "XAUT", "name": "Tether Gold",
                "circulating_supply": 5, "total_supply": 10, "max_supply": None,
                "quotes": {"USD": {"price": 2.0, "market_cap": 10.0, "volume_24h": 3.0}},
            },
        ]
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps(payload).encode("utf-8")
        with patch.object(MODULE.urllib.request, "urlopen", return_value=response):
            rows, mode, error_code, scanned, matches = MODULE._fetch_commodity_markets("usd", 5)
        self.assertEqual(mode, "live")
        self.assertEqual(error_code, 0)
        self.assertEqual(scanned, 1)
        self.assertEqual(matches, 1)
        self.assertIsNone(rows[0]["fully_diluted_valuation"])




if __name__ == "__main__":
    unittest.main()
