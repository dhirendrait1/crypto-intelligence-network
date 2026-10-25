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



class FiniteNumericValidationTests(unittest.TestCase):
    def test_oversized_integer_is_treated_as_missing(self):
        self.assertIsNone(MODULE._number(10**10000))

    def test_oversized_price_is_not_exposed_and_scores_zero(self):
        scored = MODULE._score({
            "id": "huge-price", "symbol": "HUGE", "name": "Huge Price",
            "current_price": 10**10000,
        })
        self.assertIsNone(scored["price"])
        self.assertEqual(scored["screen_score"], 0)

    def test_non_finite_provider_values_are_treated_as_missing(self):
        for value in (float("nan"), float("inf"), float("-inf"), True, "12.5", None):
            with self.subTest(value=value):
                self.assertIsNone(MODULE._number(value))

    def test_finite_numeric_provider_values_are_preserved(self):
        for value in (0, 12, 12.5, -2.0):
            with self.subTest(value=value):
                self.assertEqual(MODULE._number(value), float(value))

    def test_screening_price_does_not_expose_non_finite_provider_value(self):
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value):
                scored = MODULE._score({
                    "id": "test-coin", "symbol": "TST", "name": "Test Coin",
                    "current_price": value,
                })
                self.assertIsNone(scored["price"])
                self.assertEqual(scored["screen_score"], 0)

class ScreeningDataQualityPropagationTests(unittest.TestCase):
    def test_stale_or_unknown_timestamps_hold_candidate_signal(self):
        for timestamp, expected in (("2020-01-01T00:00:00Z", "stale"), (None, "unknown"), ("bad-time", "unknown")):
            with self.subTest(timestamp=timestamp):
                result = MODULE._score({
                    "id": "example", "symbol": "ABC", "name": "Example",
                    "current_price": 1.0, "market_cap": 500_000_000,
                    "total_volume": 20_000_000, "fully_diluted_valuation": 600_000_000,
                    "circulating_supply": 80_000_000, "total_supply": 100_000_000,
                    "price_change_percentage_24h": 2.0, "last_updated": timestamp,
                })
                self.assertEqual(result["freshness_status"], expected)
                self.assertFalse(result["analysis_eligible"])
                self.assertEqual(result["screen_band"], "data_quality_hold")
                self.assertFalse(result["screening_eligible"])
                self.assertTrue(any("candidate signal held" in warning for warning in result["warnings"]))

    def test_fresh_positive_price_is_analysis_eligible(self):
        timestamp = MODULE.datetime.now(MODULE.timezone.utc).isoformat().replace("+00:00", "Z")
        result = MODULE._score({
            "id": "example", "symbol": "ABC", "name": "Example",
            "current_price": 1.0, "last_updated": timestamp,
        })
        self.assertEqual(result["freshness_status"], "fresh")
        self.assertTrue(result["analysis_eligible"])
        self.assertNotEqual(result["screen_band"], "data_quality_hold")

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


class ProviderFallbackNumericQualityTests(unittest.TestCase):
    def test_coinpaprika_fallback_omits_malformed_numeric_metrics(self):
        payload = [
            {
                "id": "malformed-coin", "symbol": "BAD", "name": "Malformed Coin",
                "circulating_supply": "unknown", "total_supply": -10, "max_supply": "many",
                "last_updated": "2026-10-24T00:00:00Z",
                "quotes": {"USD": {"price": "1.5", "market_cap": "not-a-number",
                    "volume_24h": float("inf"), "percent_change_24h": True}},
            },
            {
                "id": "valid-coin", "symbol": "VAL", "name": "Valid Coin",
                "circulating_supply": 5, "total_supply": 10, "max_supply": 20,
                "last_updated": "2026-10-24T00:00:00Z",
                "quotes": {"USD": {"price": 2.0, "market_cap": 100.0,
                    "volume_24h": 10.0, "percent_change_24h": 1.0}},
            },
        ]
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps(payload).encode("utf-8")
        primary_error = MODULE.urllib.error.HTTPError(
            "https://api.coingecko.com/api/v3/coins/markets", 503, "unavailable", {}, None
        )
        with patch.object(MODULE.urllib.request, "urlopen", side_effect=[primary_error, response]):
            rows = MODULE._request_markets("usd", 10)
        by_id = {row["id"]: row for row in rows}
        malformed = by_id["malformed-coin"]
        self.assertIsNone(malformed["current_price"])
        self.assertIsNone(malformed["market_cap"])
        self.assertIsNone(malformed["total_volume"])
        self.assertIsNone(malformed["fully_diluted_valuation"])
        self.assertIsNone(malformed["circulating_supply"])
        self.assertIsNone(malformed["total_supply"])
        self.assertIsNone(malformed["price_change_percentage_24h"])
        self.assertEqual(by_id["valid-coin"]["market_cap"], 100.0)
        self.assertEqual(by_id["valid-coin"]["fully_diluted_valuation"], 40.0)
        self.assertEqual(malformed["_cin_provider"], "CoinPaprika")
        self.assertEqual(malformed["_cin_quote_currency"], "USD")
        self.assertEqual(by_id["valid-coin"]["_cin_quote_currency"], "USD")

    def test_coinpaprika_fallback_skips_malformed_quote_containers(self):
        payload = [
            {"id": "bad-quotes", "symbol": "BAD", "name": "Bad Quotes", "quotes": []},
            {"id": "good-quotes", "symbol": "GOOD", "name": "Good Quotes",
             "quotes": {"USD": {"price": 2, "market_cap": 20, "volume_24h": 3}}},
        ]
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps(payload).encode("utf-8")
        primary_error = MODULE.urllib.error.HTTPError(
            "https://api.coingecko.com/api/v3/coins/markets", 503, "unavailable", {}, None
        )
        with patch.object(MODULE.urllib.request, "urlopen", side_effect=[primary_error, response]):
            rows = MODULE._request_markets("usd", 10)
        self.assertEqual([row["id"] for row in rows], ["good-quotes"])

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
            rows, mode, error_code, scanned, matches, details, retrieved_at = MODULE._fetch_commodity_markets("usd", 5)
        self.assertEqual(mode, "live")
        self.assertEqual(error_code, 0)
        self.assertEqual(scanned, 1)
        self.assertEqual(matches, 1)
        self.assertIsNone(rows[0]["fully_diluted_valuation"])


class RetrievalTimestampFormattingTests(unittest.TestCase):
    def test_invalid_and_oversized_retrieval_timestamps_are_missing(self):
        for value in (None, True, float('inf'), 10**10000, '123'):
            with self.subTest(value_type=type(value).__name__):
                self.assertIsNone(MODULE._safe_retrieved_at(value))

    def test_epoch_retrieval_timestamp_is_formatted_in_utc(self):
        self.assertEqual(
            MODULE._safe_retrieved_at(0),
            '1970-01-01T00:00:00+00:00',
        )

class ScreeningFreshnessTests(unittest.TestCase):
    def setUp(self):
        MODULE._CACHE.clear()

    def tearDown(self):
        MODULE._CACHE.clear()

    def test_provider_retrieval_timestamp_is_preserved_and_cache_age_is_measurable(self):
        fixture = [{
            "id": "fresh-coin", "symbol": "FRSH", "name": "Fresh Coin",
            "_cin_provider": "CoinGecko", "_cin_quote_currency": "USD",
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
        self.assertEqual(output["provider"], "CoinGecko")
        self.assertEqual(output["quote_currency"], "USD")
        rows_cached, cached_mode, cached_error, cached_details = MODULE._fetch_markets("usd", 1)
        self.assertEqual(cached_mode, "cache")
        self.assertEqual(cached_error, 0)
        self.assertEqual(rows_cached[0]["_cin_retrieved_at"], rows[0]["_cin_retrieved_at"])
        self.assertEqual(rows_cached[0]["_cin_provider"], "CoinGecko")
        self.assertEqual(rows_cached[0]["_cin_quote_currency"], "USD")
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

    async def test_commodity_endpoint_exposes_provenance_for_empty_scan(self):
        retrieved_at = MODULE.time.time() - 5
        async def fake_to_thread(func, *args, **kwargs):
            return ([], "live", 0, 250, 0, None, retrieved_at)
        with patch.object(MODULE.asyncio, "to_thread", side_effect=fake_to_thread):
            response = await MODULE.coin_screening(
                vs_currency="usd", per_page=5, min_score=0, asset_type="commodity_backed"
            )
        self.assertEqual(response["count"], 0)
        self.assertEqual(response["data_mode"], "live")
        self.assertEqual(response["universe_scan"]["scanned_universe_count"], 250)
        self.assertEqual(response["universe_scan"]["classified_match_count"], 0)
        self.assertIsNotNone(response["universe_scan"]["provider_retrieved_at"])
        self.assertGreaterEqual(response["cache_age_seconds"], 5)

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
            return ([row], "stale_cache", 0, 500, 2, details, row["_cin_retrieved_at"])

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


class CacheFreshnessContractTests(unittest.TestCase):
    def setUp(self):
        MODULE._CACHE.clear()

    def tearDown(self):
        MODULE._CACHE.clear()

    def test_stale_cache_state_does_not_overwrite_provider_timestamp_quality(self):
        import asyncio
        provider_time = MODULE.datetime.now(MODULE.timezone.utc).isoformat().replace("+00:00", "Z")
        retrieved_at = MODULE.time.time() - 120
        row = {
            "id": "example", "symbol": "ABC", "name": "Example",
            "current_price": 1.0, "market_cap": 500_000_000,
            "total_volume": 20_000_000, "fully_diluted_valuation": 600_000_000,
            "circulating_supply": 80_000_000, "total_supply": 100_000_000,
            "price_change_percentage_24h": 2.0, "last_updated": provider_time,
            "_cin_provider": "CoinGecko", "_cin_quote_currency": "USD",
            "_cin_retrieved_at": retrieved_at,
        }
        with patch.object(MODULE, "_fetch_markets", return_value=([row], "stale_cache", 0, {
            "primary_provider": "CoinGecko", "primary_error": "network_error",
            "primary_http_status": None, "fallback_provider": "CoinPaprika",
            "fallback_error": "network_error", "fallback_http_status": None,
        })):
            response = asyncio.run(MODULE.coin_screening(vs_currency="usd", per_page=1, min_score=0, asset_type="all"))

        result = response["data"][0]
        self.assertEqual(result["freshness_status"], "stale_cache")
        self.assertEqual(result["provider_timestamp_status"], "fresh")
        self.assertIsNotNone(result["provider_timestamp_age_seconds"])
        self.assertFalse(result["analysis_eligible"])
        self.assertFalse(result["screening_eligible"])
        self.assertEqual(response["data_mode"], "stale_cache")


class ScreeningArithmeticSafetyTests(unittest.TestCase):
    def test_negative_financial_magnitudes_are_missing_evidence(self):
        result = MODULE._score({
            "id": "negative", "symbol": "NEG", "name": "Negative Metrics",
            "current_price": 1.0, "last_updated": MODULE.datetime.now(MODULE.timezone.utc).isoformat(),
            "market_cap": -100.0, "total_volume": -50.0,
            "fully_diluted_valuation": -200.0, "circulating_supply": -10.0,
            "total_supply": -20.0,
        })
        for field in ("market_cap", "total_volume_24h", "fully_diluted_valuation", "circulating_supply_ratio", "volume_to_market_cap", "fdv_gap_ratio"):
            with self.subTest(field=field):
                self.assertIsNone(result[field])
        self.assertTrue(any("Market-cap data missing" in warning for warning in result["warnings"]))

    def test_overflowing_volume_and_supply_ratios_are_not_emitted(self):
        result = MODULE._score({
            "id": "overflow", "symbol": "OVR", "name": "Overflow Metrics",
            "current_price": 1.0, "last_updated": MODULE.datetime.now(MODULE.timezone.utc).isoformat(),
            "market_cap": 1e-308, "total_volume": 1e308,
            "fully_diluted_valuation": 1e308, "circulating_supply": 1e308,
            "total_supply": 1e-308,
        })
        self.assertIsNone(result["volume_to_market_cap"])
        self.assertIsNone(result["circulating_supply_ratio"])
        self.assertTrue(any("non-finite" in warning for warning in result["warnings"]))
        self.assertTrue(all(
            value is None or (not isinstance(value, float) or MODULE.math.isfinite(value))
            for value in result.values()
        ))


class MarketIdentityDeterminismTests(unittest.TestCase):
    def test_identity_less_rows_are_discarded_and_duplicate_ids_keep_first_row(self):
        rows = [
            {"id": "bitcoin", "symbol": "BTC", "current_price": 100},
            {"id": "BITCOIN", "symbol": "BTC", "current_price": 101},
            {"id": "  ", "symbol": "BAD"},
            {"symbol": "NOID"},
            {"id": "ethereum", "symbol": "ETH"},
        ]
        accepted, quality = MODULE._canonical_market_rows(rows)
        self.assertEqual([row["id"] for row in accepted], ["bitcoin", "ethereum"])
        self.assertEqual(accepted[0]["current_price"], 100)
        self.assertEqual(quality, {
            "input_row_count": 5,
            "invalid_identity_count": 2,
            "duplicate_id_count": 1,
            "unique_identity_count": 2,
        })

    def test_empty_input_returns_empty_rows_and_zero_counts(self):
        self.assertEqual(MODULE._canonical_market_rows([]), ([], {
            "input_row_count": 0, "invalid_identity_count": 0,
            "duplicate_id_count": 0, "unique_identity_count": 0,
        }))


class MarketCacheProvenanceTests(unittest.TestCase):
    def setUp(self):
        MODULE._CACHE.clear()

    def tearDown(self):
        MODULE._CACHE.clear()

    def test_cache_hit_preserves_original_retrieval_timestamp_and_currency_isolation(self):
        usd_rows = [{"id": "bitcoin", "current_price": 100, "_cin_provider": "CoinGecko", "_cin_quote_currency": "USD"}]
        eur_rows = [{"id": "bitcoin", "current_price": 90, "_cin_provider": "CoinGecko", "_cin_quote_currency": "EUR"}]
        with patch.object(MODULE, "_request_markets", side_effect=[usd_rows, eur_rows]) as request:
            first, first_mode, _, _ = MODULE._fetch_markets("usd", 1)
            original_retrieved_at = first[0]["_cin_retrieved_at"]
            second, second_mode, _, _ = MODULE._fetch_markets("usd", 1)
            euro, euro_mode, _, _ = MODULE._fetch_markets("eur", 1)

        self.assertEqual(first_mode, "live")
        self.assertEqual(second_mode, "cache")
        self.assertEqual(euro_mode, "live")
        self.assertEqual(second[0]["_cin_retrieved_at"], original_retrieved_at)
        self.assertEqual(second[0]["_cin_quote_currency"], "USD")
        self.assertEqual(euro[0]["_cin_quote_currency"], "EUR")
        self.assertEqual(request.call_count, 2)



class MarketProviderResponseSizeTests(unittest.TestCase):
    def test_primary_and_fallback_provider_bodies_are_bounded(self):
        class OversizedResponse:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self, size=-1):
                self.requested_size = size
                return b"x" * size

        primary = OversizedResponse()
        fallback = OversizedResponse()
        with patch.object(MODULE.urllib.request, "urlopen", side_effect=[primary, fallback]):
            with self.assertRaises(MODULE.MarketDataProviderFailure) as caught:
                MODULE._request_markets("usd", 5)

        self.assertEqual(primary.requested_size, MODULE._MAX_MARKET_PROVIDER_RESPONSE_BYTES + 1)
        self.assertEqual(fallback.requested_size, MODULE._MAX_MARKET_PROVIDER_RESPONSE_BYTES + 1)
        self.assertEqual(caught.exception.primary_kind, "invalid_response")
        self.assertEqual(caught.exception.fallback_kind, "invalid_response")
