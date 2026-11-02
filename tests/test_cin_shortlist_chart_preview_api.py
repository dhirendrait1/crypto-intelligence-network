import asyncio
import os
import unittest
from unittest.mock import AsyncMock, patch
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
import cin_shortlist_chart_preview_api as api

class ChartPreviewTests(unittest.TestCase):
    def setUp(self):
        api._cache.clear()
        api._failures.clear()
        self.news_patcher = patch.object(api, "news_sentiment", new_callable=AsyncMock, side_effect=ValueError("unavailable"))
        self.news_patcher.start()
        self.addCleanup(self.news_patcher.stop)

    @patch.dict(os.environ, {}, clear=True)
    def test_disabled_never_fetches(self):
        with patch.object(api, "get_market_candles", new_callable=AsyncMock) as fetch:
            with self.assertRaises(HTTPException) as error:
                asyncio.run(api.shortlist_chart_preview("bitcoin", "24h"))
        self.assertEqual(error.exception.status_code, 404)
        fetch.assert_not_called()

    @patch.dict(os.environ, {"CIN_SHORTLIST_PREVIEW_ENABLED": "1"}, clear=True)
    def test_validated_chart_is_not_a_complete_shortlist(self):
        async def run():
            with patch.object(api, "get_market_candles", new_callable=AsyncMock, return_value={"data": []}) as fetch:
                with patch.object(api, "chart_evidence", return_value={
                    "status": "available", "window_end": datetime.now(timezone.utc).isoformat()
                }) as validate:
                    first = await api.shortlist_chart_preview("bitcoin", "6h")
                    second = await api.shortlist_chart_preview("bitcoin", "6h")
                    self.assertEqual(first["shortlist_status"], "not_eligible")
                    self.assertIn("social", first["missing_required_evidence"])
                    self.assertIsNone(first["probability"])
                    self.assertEqual(second["chart"]["status"], "available")
                    fetch.assert_awaited_once_with(symbol="BTCUSDT", interval="15m", limit=26)
                    validate.assert_called_once()
        asyncio.run(run())

    @patch.dict(os.environ, {"CIN_SHORTLIST_PREVIEW_ENABLED": "1"}, clear=True)
    def test_stale_cached_chart_is_not_returned_as_available(self):
        async def run():
            stale = (datetime.now(timezone.utc) - timedelta(minutes=6)).isoformat()
            current = datetime.now(timezone.utc).isoformat()
            with patch.object(api, "get_market_candles", new_callable=AsyncMock, return_value={"data": []}) as fetch:
                with patch.object(api, "chart_evidence", side_effect=[
                    {"status": "available", "window_end": stale},
                    {"status": "available", "window_end": current},
                ]):
                    await api.shortlist_chart_preview("bitcoin", "1h")
                    result = await api.shortlist_chart_preview("bitcoin", "1h")
            self.assertEqual(result["chart"]["window_end"], current)
            self.assertEqual(fetch.await_count, 2)
        asyncio.run(run())

    def test_invalid_or_future_cached_timestamp_is_not_fresh(self):
        now = datetime.now(timezone.utc)
        for stamp in ("bad", None, (now + timedelta(seconds=1)).isoformat()):
            with self.subTest(stamp=stamp):
                self.assertFalse(api._chart_is_fresh({"chart": {"window_end": stamp}}, "1h", now))

    @patch.dict(os.environ, {"CIN_SHORTLIST_PREVIEW_ENABLED": "1"}, clear=True)
    def test_preliminary_news_does_not_pass_news_gate(self):
        async def run():
            now = datetime.now(timezone.utc).isoformat()
            payload = {"query": "bitcoin", "source": "GDELT DOC 2.0 public article search", "count": 1,
                       "articles": [{"title": "Bitcoin network update", "url": "https://example.test/news",
                                     "provider_seen_at_utc": now, "provider_seen_at_validation_status": "valid"}]}
            with patch.object(api, "get_market_candles", new_callable=AsyncMock, return_value={}):
                with patch.object(api, "chart_evidence", return_value={"status": "available", "window_end": now}):
                    with patch.object(api, "news_sentiment", new_callable=AsyncMock, return_value=payload) as fetch:
                        result = await api.shortlist_chart_preview("bitcoin", "24h")
            fetch.assert_awaited_once_with(query="bitcoin", max_records=10)
            self.assertEqual(result["news"]["status"], "preliminary")
            self.assertIn("news", result["missing_required_evidence"])
            self.assertEqual(result["shortlist_status"], "not_eligible")
        asyncio.run(run())

    @patch.dict(os.environ, {"CIN_SHORTLIST_PREVIEW_ENABLED": "1"}, clear=True)
    def test_invalid_input_never_fetches(self):
        with patch.object(api, "get_market_candles", new_callable=AsyncMock) as fetch:
            with self.assertRaises(HTTPException) as error:
                asyncio.run(api.shortlist_chart_preview("unknown", "24h"))
        self.assertEqual(error.exception.status_code, 400)
        fetch.assert_not_called()

    @patch.dict(os.environ, {"CIN_SHORTLIST_PREVIEW_ENABLED": "1"}, clear=True)
    def test_usd_joins_only_exact_coinbase_usd_and_keeps_other_requirements_missing(self):
        async def run():
            now = datetime.now(timezone.utc).isoformat()
            market_payload = {
                "source": "Coinbase Exchange public API", "currency": "USD", "count": 1,
                "data": [{"id": "bitcoin", "symbol": "BTC", "currency": "USD",
                          "product_id": "BTC-USD", "price": 70000, "last_updated": now,
                          "freshness_status": "fresh", "analysis_eligible": True}],
            }
            chart = {"status": "available", "market_id": "BTCUSD", "window_end": now}
            with patch.object(api, "get_market_candles", new_callable=AsyncMock, return_value={}) as fetch:
                with patch.object(api, "chart_evidence", return_value=chart):
                    with patch.object(api, "get_public_market_data", new_callable=AsyncMock, return_value=market_payload):
                        result = await api.shortlist_chart_preview("bitcoin", "24h", "USD")
            fetch.assert_awaited_once_with(symbol="BTCUSD", interval="1h", limit=26)
            self.assertEqual(result["market"]["market_id"], "BTCUSD")
            self.assertNotIn("market", result["missing_required_evidence"])
            self.assertIn("social", result["missing_required_evidence"])
            self.assertEqual(result["shortlist_status"], "not_eligible")
            self.assertIsNone(result["probability"])
        asyncio.run(run())

    @patch.dict(os.environ, {"CIN_SHORTLIST_PREVIEW_ENABLED": "1"}, clear=True)
    def test_usdt_does_not_fetch_or_substitute_usd_price(self):
        async def run():
            with patch.object(api, "get_market_candles", new_callable=AsyncMock, return_value={}):
                with patch.object(api, "chart_evidence", return_value={"status": "available"}):
                    with patch.object(api, "get_public_market_data", new_callable=AsyncMock) as market:
                        result = await api.shortlist_chart_preview("bitcoin", "24h", "USDT")
            market.assert_not_called()
            self.assertIsNone(result["market"])
            self.assertIn("market", result["missing_required_evidence"])
        asyncio.run(run())

    @patch.dict(os.environ, {"CIN_SHORTLIST_PREVIEW_ENABLED": "1"}, clear=True)
    def test_price_provider_failure_keeps_chart_but_not_market(self):
        async def run():
            with patch.object(api, "get_market_candles", new_callable=AsyncMock, return_value={}):
                with patch.object(api, "chart_evidence", return_value={"status": "available"}):
                    with patch.object(api, "get_public_market_data", new_callable=AsyncMock, side_effect=ValueError("private")):
                        result = await api.shortlist_chart_preview("bitcoin", "24h", "USD")
            self.assertEqual(result["chart"]["status"], "available")
            self.assertIsNone(result["market"])
            self.assertIn("market", result["missing_required_evidence"])
        asyncio.run(run())

    @patch.dict(os.environ, {"CIN_SHORTLIST_PREVIEW_ENABLED": "1"}, clear=True)
    def test_cached_usd_market_expires_independently_from_chart(self):
        async def run():
            now = datetime.now(timezone.utc)
            key = ("bitcoin", "24h", "USD")
            api._cache[key] = (api.time.monotonic(), {
                "chart": {"window_end": now.isoformat()},
                "market": {"observed_at": (now - timedelta(minutes=16)).isoformat()},
                "missing_required_evidence": ["news", "social", "market_sentiment"],
            })
            with patch.object(api, "get_market_candles", new_callable=AsyncMock) as fetch:
                result = await api.shortlist_chart_preview("bitcoin", "24h", "USD")
            fetch.assert_not_called()
            self.assertIsNone(result["market"])
            self.assertIn("market", result["missing_required_evidence"])
        asyncio.run(run())

    @patch.dict(os.environ, {"CIN_SHORTLIST_PREVIEW_ENABLED": "1"}, clear=True)
    def test_quote_is_part_of_cache_key(self):
        async def run():
            now = datetime.now(timezone.utc).isoformat()
            with patch.object(api, "get_market_candles", new_callable=AsyncMock, return_value={}) as fetch:
                with patch.object(api, "chart_evidence", return_value={"status": "available", "window_end": now}):
                    with patch.object(api, "get_public_market_data", new_callable=AsyncMock, side_effect=ValueError("unavailable")):
                        await api.shortlist_chart_preview("bitcoin", "24h", "USD")
                        await api.shortlist_chart_preview("bitcoin", "24h", "USDT")
            self.assertEqual(fetch.await_count, 2)
            self.assertEqual(fetch.await_args_list[0].kwargs["symbol"], "BTCUSD")
            self.assertEqual(fetch.await_args_list[1].kwargs["symbol"], "BTCUSDT")
        asyncio.run(run())

    @patch.dict(os.environ, {"CIN_SHORTLIST_PREVIEW_ENABLED": "1"}, clear=True)
    def test_real_validator_processes_provider_shaped_data(self):
        duration = 900_000
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        end = (now_ms // duration) * duration
        rows = []
        for i in range(26):
            start = end - (26 - i) * duration
            rows.append({"open_time": start, "close_time": start + duration - 1,
                         "open": 100, "high": 103, "low": 99, "close": 102,
                         "is_closed": True})
        payload = {"symbol": "BTCUSDT", "timeframe": "15m",
                   "pair_metadata_status": "identified", "quote_currency": "USDT",
                   "source": "Test provider", "source_endpoint": "https://example.test",
                   "count": len(rows), "data": rows}
        with patch.object(api, "get_market_candles", new_callable=AsyncMock, return_value=payload):
            result = asyncio.run(api.shortlist_chart_preview("bitcoin", "6h"))
        self.assertEqual(result["chart"]["candle_count"], 24)
        self.assertEqual(result["shortlist_status"], "not_eligible")
        self.assertIn("social", result["missing_required_evidence"])

    @patch.dict(os.environ, {"CIN_SHORTLIST_PREVIEW_ENABLED": "1"}, clear=True)
    def test_provider_error_is_sanitized(self):
        async def run():
            with patch.object(api, "get_market_candles", new_callable=AsyncMock, side_effect=ValueError("private detail")) as fetch:
                for _ in range(2):
                    with self.assertRaises(HTTPException) as error:
                        await api.shortlist_chart_preview("bitcoin", "24h")
                    self.assertEqual(error.exception.status_code, 503)
                    self.assertNotIn("private", error.exception.detail)
                fetch.assert_awaited_once()
        asyncio.run(run())


