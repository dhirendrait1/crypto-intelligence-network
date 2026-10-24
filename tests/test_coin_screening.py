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
            rows, mode, error_code, scanned, matches, details, retrieved_at = MODULE._fetch_commodity_markets("usd", 1)
        self.assertEqual(mode, "live")
        self.assertEqual(error_code, 0)
        self.assertEqual(scanned, 3)
        self.assertEqual(matches, 2)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["symbol"], "XAUT")
        self.assertEqual(rows[0]["_cin_scanned_universe"], 3)


class CommodityStaleCacheTests(unittest.TestCase):
    def setUp(self):
        MODULE._CACHE.clear()
        MODULE._COMMODITY_SCAN_META.clear()

    def tearDown(self):
        MODULE._CACHE.clear()
        MODULE._COMMODITY_SCAN_META.clear()

    def test_empty_scan_is_cached_with_timestamp_and_universe_counts(self):
        payload = [
            {"id": "btc-bitcoin", "symbol": "BTC", "name": "Bitcoin",
             "quotes": {"USD": {"price": 100, "market_cap": 1000, "volume_24h": 10}}},
            {"id": "eth-ethereum", "symbol": "ETH", "name": "Ethereum",
             "quotes": {"USD": {"price": 10, "market_cap": 500, "volume_24h": 5}}},
        ]
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps(payload).encode("utf-8")
        with patch.object(MODULE.urllib.request, "urlopen", return_value=response):
            rows, mode, _, scanned, matches, _, retrieved_at = MODULE._fetch_commodity_markets("usd", 2)
        self.assertEqual(rows, [])
        self.assertEqual(mode, "live")
        self.assertEqual(scanned, 2)
        self.assertEqual(matches, 0)
        self.assertIsInstance(retrieved_at, (int, float))

        with patch.object(MODULE.urllib.request, "urlopen", side_effect=AssertionError("cache should be used")):
            cached, cached_mode, _, cached_scanned, cached_matches, _, cached_at = MODULE._fetch_commodity_markets("usd", 2)
        self.assertEqual(cached, [])
        self.assertEqual(cached_mode, "cache")
        self.assertEqual(cached_scanned, 2)
        self.assertEqual(cached_matches, 0)
        self.assertEqual(cached_at, retrieved_at)

    def test_network_failure_uses_stale_cache_with_structured_provenance(self):
        old_time = MODULE.time.time() - 120
        cached_row = {
            "id": "tether-gold", "symbol": "XAUT", "name": "Tether Gold",
            "_cin_provider": "CoinPaprika", "_cin_retrieved_at": old_time,
            "_cin_scanned_universe": 500, "_cin_match_count": 2,
        }
        MODULE._CACHE[("commodity:usd", 5)] = (old_time, [cached_row])
        with patch.object(MODULE.urllib.request, "urlopen", side_effect=MODULE.urllib.error.URLError("offline")):
            rows, mode, error_code, scanned, matches, details, retrieved_at = MODULE._fetch_commodity_markets("usd", 5)

        self.assertEqual(mode, "stale_cache")
        self.assertEqual(error_code, 0)
        self.assertEqual(scanned, 500)
        self.assertEqual(matches, 2)
        self.assertEqual(rows[0]["_cin_retrieved_at"], old_time)
        self.assertEqual(details["primary_provider"], "CoinPaprika")
        self.assertEqual(details["primary_error"], "network_error")
        self.assertIsNone(details["primary_http_status"])


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
            rows, mode, error_code, scanned, matches, details = MODULE._fetch_commodity_markets("usd", 5)
        self.assertEqual(mode, "live")
        self.assertEqual(error_code, 0)
        self.assertEqual(scanned, 1)
        self.assertEqual(matches, 1)
        self.assertIsNone(rows[0]["fully_diluted_valuation"])


class ScreeningFreshnessTests(unittest.TestCase):
    def setUp(self):
        MODULE._CACHE.clear()

    def tearDown(self):
        MODULE._CACHE.clear()

    def test_provider_retrieval_timestamp_is_preserved_and_cache_age_is_measurable(self):
        fixture = [{
            "id": "fresh-coin", "symbol": "FRSH", "name": "Fresh Coin",
            "current_price": 2.0, "market_cap": 100.0, "total_volume": 10.0,
            "fully_diluted_valuation": 120.0, "circulating_supply": 40.0,
            "total_supply": 50.0, "price_change_percentage_24h": 1.0,
            "last_updated": "2026-10-24T00:00:00Z",
        }]
        with patch.object(MODULE, "_request_markets", return_value=fixture):
            rows, mode, error_code, error_details = MODULE._fetch_markets("usd", 1)
        self.assertEqual(mode, "live")
        self.assertEqual(error_code, 0)
        self.assertIsInstance(rows[0].get("_cin_retrieved_at"), (int, float))
        output = MODULE._score(rows[0])
        self.assertIsNotNone(output["provider_retrieved_at"])
        rows_cached, cached_mode, cached_error, cached_details = MODULE._fetch_markets("usd", 1)
        self.assertEqual(cached_mode, "cache")
        self.assertEqual(cached_error, 0)
        self.assertEqual(rows_cached[0]["_cin_retrieved_at"], rows[0]["_cin_retrieved_at"])
        self.assertIsNone(cached_details)




class ProviderFailureClassificationTests(unittest.TestCase):
    def test_http_failure_classification_keeps_status_code(self):
        error = MODULE.urllib.error.HTTPError("provider", 429, "limited", {}, None)
        self.assertEqual(MODULE._failure_kind(error), ("http_error", 429))

    def test_network_failure_classification_has_no_http_status(self):
        error = MODULE.urllib.error.URLError("offline")
        self.assertEqual(MODULE._failure_kind(error), ("network_error", None))

    def test_invalid_response_classification_has_no_http_status(self):
        self.assertEqual(MODULE._failure_kind(ValueError("invalid")), ("invalid_response", None))


    def test_primary_and_fallback_http_failures_preserve_both_statuses(self):
        primary = MODULE.urllib.error.HTTPError("coingecko", 429, "limited", {}, None)
        fallback = MODULE.urllib.error.HTTPError("coinpaprika", 503, "unavailable", {}, None)
        with patch.object(MODULE.urllib.request, "urlopen", side_effect=[primary, fallback]):
            with self.assertRaises(MODULE.MarketDataProviderFailure) as caught:
                MODULE._request_markets("usd", 5)
        failure = caught.exception
        self.assertEqual(failure.primary_kind, "http_error")
        self.assertEqual(failure.primary_status, 429)
        self.assertEqual(failure.fallback_kind, "http_error")
        self.assertEqual(failure.fallback_status, 503)


    def test_invalid_primary_payload_and_fallback_network_failure_are_distinct(self):
        import io
        primary_response = type(
            "Response", (), {
                "__enter__": lambda self: self,
                "__exit__": lambda self, *args: False,
                "read": lambda self: b"{}",
            }
        )()
        fallback = MODULE.urllib.error.URLError("offline")
        with patch.object(MODULE.urllib.request, "urlopen", side_effect=[primary_response, fallback]):
            with self.assertRaises(MODULE.MarketDataProviderFailure) as caught:
                MODULE._request_markets("usd", 5)
        failure = caught.exception
        self.assertEqual(failure.primary_kind, "invalid_response")
        self.assertIsNone(failure.primary_status)
        self.assertEqual(failure.fallback_kind, "network_error")
        self.assertIsNone(failure.fallback_status)


    def test_stale_cache_is_used_after_both_providers_fail_and_timestamp_survives(self):
        MODULE._CACHE.clear()
        now = 1_800_000_000.0
        cached_rows = [{
            "id": "cached-coin", "symbol": "CACH", "name": "Cached Coin",
            "_cin_retrieved_at": now - 120,
        }]
        MODULE._CACHE[("usd", 5)] = (now - 120, cached_rows)
        failure = MODULE.MarketDataProviderFailure(
            primary_kind="http_error", primary_status=429,
            fallback_kind="http_error", fallback_status=503,
        )
        with patch.object(MODULE.time, "time", return_value=now), patch.object(
            MODULE, "_request_markets", side_effect=failure
        ):
            rows, mode, error_code, error_details = MODULE._fetch_markets("usd", 5)
        self.assertEqual(mode, "stale_cache")
        self.assertEqual(error_code, 503)
        self.assertEqual(error_details["primary_http_status"], 429)
        self.assertEqual(error_details["fallback_http_status"], 503)
        self.assertEqual(error_details["primary_error"], "http_error")
        self.assertEqual(error_details["fallback_error"], "http_error")
        self.assertEqual(rows[0]["_cin_retrieved_at"], now - 120)
        MODULE._CACHE.clear()

    def test_both_provider_failure_without_cache_propagates_structured_error(self):
        MODULE._CACHE.clear()
        failure = MODULE.MarketDataProviderFailure(
            primary_kind="http_error", primary_status=429,
            fallback_kind="http_error", fallback_status=503,
        )
        with patch.object(MODULE, "_request_markets", side_effect=failure):
            with self.assertRaises(MODULE.MarketDataProviderFailure) as caught:
                MODULE._fetch_markets("usd", 5)
        self.assertEqual(caught.exception.primary_status, 429)
        self.assertEqual(caught.exception.fallback_status, 503)
        MODULE._CACHE.clear()


class ScreeningResponseMetadataTests(unittest.IsolatedAsyncioTestCase):
    async def test_endpoint_marks_fresh_response_without_provider_errors(self):
        row = {
            "id": "fresh-coin", "symbol": "FRSH", "name": "Fresh Coin",
            "current_price": 2.0, "market_cap": 100.0, "total_volume": 10.0,
            "fully_diluted_valuation": 120.0, "circulating_supply": 40.0,
            "total_supply": 50.0, "price_change_percentage_24h": 1.0,
            "last_updated": "2026-10-24T00:00:00Z",
            "_cin_provider": "CoinGecko", "_cin_retrieved_at": MODULE.time.time(),
        }

        async def fake_to_thread(func, *args, **kwargs):
            return ([row], "live", 0, None)

        with patch.object(MODULE.asyncio, "to_thread", side_effect=fake_to_thread):
            response = await MODULE.coin_screening(
                vs_currency="usd", per_page=1, min_score=0, asset_type="all"
            )

        self.assertEqual(response["data_mode"], "live")
        self.assertIsNone(response["provider_error_code"])
        self.assertIsNone(response["provider_error_details"])
        self.assertIsNone(response["stale_data_warning"])
        self.assertIsNotNone(response["cache_age_seconds"])
        self.assertIsInstance(response["data"], list)

    async def test_endpoint_preserves_provider_timestamp_for_fresh_cache(self):
        retrieved_at = MODULE.time.time() - 30
        row = {
            "id": "cached-fresh-coin", "symbol": "CFRS", "name": "Cached Fresh Coin",
            "current_price": 2.0, "market_cap": 100.0, "total_volume": 10.0,
            "fully_diluted_valuation": 120.0, "circulating_supply": 40.0,
            "total_supply": 50.0, "price_change_percentage_24h": 1.0,
            "last_updated": "2026-10-24T00:00:00Z",
            "_cin_provider": "CoinGecko", "_cin_retrieved_at": retrieved_at,
        }

        async def fake_to_thread(func, *args, **kwargs):
            return ([row], "cache", 0, None)

        with patch.object(MODULE.asyncio, "to_thread", side_effect=fake_to_thread):
            response = await MODULE.coin_screening(
                vs_currency="usd", per_page=1, min_score=0, asset_type="all"
            )

        self.assertEqual(response["data_mode"], "cache")
        self.assertIsNone(response["provider_error_details"])
        self.assertIsNone(response["stale_data_warning"])
        self.assertEqual(response["data"][0]["provider_retrieved_at"],
                         MODULE.datetime.fromtimestamp(retrieved_at, MODULE.timezone.utc).isoformat())
        self.assertGreaterEqual(response["cache_age_seconds"], 30)
        self.assertLess(response["cache_age_seconds"], 35)

    async def test_commodity_endpoint_attributes_uncached_http_failure_to_coinpaprika(self):
        error = MODULE.urllib.error.HTTPError("coinpaprika", 429, "limited", {}, None)
        async def fake_to_thread(func, *args, **kwargs):
            raise error
        with patch.object(MODULE.asyncio, "to_thread", side_effect=fake_to_thread):
            with self.assertRaises(MODULE.HTTPException) as caught:
                await MODULE.coin_screening(
                    vs_currency="usd", per_page=5, min_score=0, asset_type="commodity_backed"
                )
        self.assertEqual(caught.exception.status_code, 503)
        self.assertEqual(caught.exception.detail["primary_provider"], "CoinPaprika")
        self.assertEqual(caught.exception.detail["primary_http_status"], 429)

    async def test_commodity_endpoint_attributes_uncached_network_failure_to_coinpaprika(self):
        error = MODULE.urllib.error.URLError("offline")
        async def fake_to_thread(func, *args, **kwargs):
            raise error
        with patch.object(MODULE.asyncio, "to_thread", side_effect=fake_to_thread):
            with self.assertRaises(MODULE.HTTPException) as caught:
                await MODULE.coin_screening(
                    vs_currency="usd", per_page=5, min_score=0, asset_type="commodity_backed"
                )
        self.assertEqual(caught.exception.status_code, 503)
        self.assertEqual(caught.exception.detail["primary_provider"], "CoinPaprika")
        self.assertEqual(caught.exception.detail["primary_error"], "network_error")

    async def test_commodity_endpoint_exposes_stale_cache_error_provenance(self):
        row = {
            "id": "tether-gold", "symbol": "XAUT", "name": "Tether Gold",
            "current_price": 2000.0, "market_cap": 100.0, "total_volume": 10.0,
            "fully_diluted_valuation": None, "circulating_supply": 10.0,
            "total_supply": 10.0, "price_change_percentage_24h": 1.0,
            "_cin_provider": "CoinPaprika", "_cin_retrieved_at": MODULE.time.time() - 120,
            "_cin_scanned_universe": 500, "_cin_match_count": 2,
        }
        details = {
            "primary_provider": "CoinPaprika", "primary_error": "network_error",
            "primary_http_status": None,
        }

        async def fake_to_thread(func, *args, **kwargs):
            return ([row], "stale_cache", 0, 500, 2, details)

        with patch.object(MODULE.asyncio, "to_thread", side_effect=fake_to_thread):
            response = await MODULE.coin_screening(
                vs_currency="usd", per_page=5, min_score=0, asset_type="commodity_backed"
            )

        self.assertEqual(response["data_mode"], "stale_cache")
        self.assertEqual(response["provider_error_details"], details)
        self.assertIsNotNone(response["stale_data_warning"])
        self.assertEqual(response["universe_scan"]["scanned_universe_count"], 500)

    async def test_endpoint_exposes_structured_stale_cache_provider_errors(self):
        row = {
            "id": "cached-coin", "symbol": "CACH", "name": "Cached Coin",
            "current_price": 2.0, "market_cap": 100.0, "total_volume": 10.0,
            "fully_diluted_valuation": None, "circulating_supply": 40.0,
            "total_supply": 50.0, "price_change_percentage_24h": 1.0,
            "_cin_provider": "CoinGecko", "_cin_retrieved_at": 1_800_000_000.0,
        }
        details = {
            "primary_provider": "CoinGecko", "primary_error": "http_error",
            "primary_http_status": 429, "fallback_provider": "CoinPaprika",
            "fallback_error": "http_error", "fallback_http_status": 503,
        }

        async def fake_to_thread(func, *args, **kwargs):
            return ([row], "stale_cache", 503, details)

        with patch.object(MODULE.asyncio, "to_thread", side_effect=fake_to_thread):
            response = await MODULE.coin_screening(
                vs_currency="usd", per_page=1, min_score=0, asset_type="all"
            )

        self.assertEqual(response["data_mode"], "stale_cache")
        self.assertEqual(response["provider_error_code"], 503)
        self.assertEqual(response["provider_error_details"], details)
        self.assertIsNotNone(response["stale_data_warning"])


if __name__ == "__main__":
    unittest.main()
