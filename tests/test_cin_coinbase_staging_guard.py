"""Security tests for disabled-by-default staging research guard."""
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from cin_coinbase_dashboard_research_api import router
from cin_coinbase_staging_guard import _LOCK, _REQUESTS, _PROVIDER_RESERVATIONS


TOKEN = "cin-staging-contract-test-token-0123456789abcdef"


def market():
    return {
        "id": "bitcoin", "symbol": "BTC", "currency": "USD", "price": 100.0,
        "last_updated": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(),
        "freshness_status": "fresh", "analysis_eligible": True,
        "total_volume_24h": 10000.0,
    }


class StagingGatewaySecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app = FastAPI()
        app.include_router(router)
        cls.client = TestClient(app)

    def setUp(self):
        self.env = patch.dict("os.environ", {
            "CIN_COINBASE_RESEARCH_ENABLED": "1",
            "CIN_COINBASE_RESEARCH_STAGE": "staging",
            "CIN_COINBASE_RESEARCH_TOKEN": TOKEN,
        })
        self.env.start()
        self.addCleanup(self.env.stop)
        with _LOCK:
            _REQUESTS.clear()
            _PROVIDER_RESERVATIONS.clear()

    def send(self, token=None):
        headers = {"Authorization": f"Bearer {token}"} if token is not None else {}
        return self.client.post("/research/coinbase/market-eligibility",
                                json={"market": market()}, headers=headers)

    @patch("cin_coinbase_dashboard_research_api.research_liquidity_with_market_status")
    def test_missing_or_incorrect_token_is_401_without_provider_call(self, provider):
        self.assertEqual(self.send().status_code, 401)
        self.assertEqual(self.send("incorrect-token").status_code, 401)
        provider.assert_not_called()

    @patch.dict("os.environ", {"CIN_COINBASE_RESEARCH_STAGE": "production"})
    @patch("cin_coinbase_dashboard_research_api.research_liquidity_with_market_status")
    def test_production_environment_always_hidden(self, provider):
        self.assertEqual(self.send(TOKEN).status_code, 404)
        provider.assert_not_called()

    @patch.dict("os.environ", {"CIN_COINBASE_RESEARCH_TOKEN": "short"})
    @patch("cin_coinbase_dashboard_research_api.research_liquidity_with_market_status")
    def test_missing_strong_config_fails_closed(self, provider):
        self.assertEqual(self.send("short").status_code, 503)
        provider.assert_not_called()

    @patch("cin_coinbase_dashboard_research_api.research_liquidity_with_market_status")
    def test_four_calls_then_rate_limit(self, provider):
        provider.return_value = {
            "status": "rejected", "product_status": "offline",
            "reason": "Not available", "execution_enabled": False,
            "book_requested": False,
        }
        for i in range(4):
            with self.subTest(i=i):
                self.assertEqual(self.send(TOKEN).status_code, 200)
        response = self.send(TOKEN)
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.headers["retry-after"], "60")
        self.assertEqual(provider.call_count, 4)

    @patch("cin_coinbase_dashboard_research_api.research_liquidity_with_market_status")
    def test_unsupported_pair_rejected_without_spending_provider_budget(self, provider):
        row = dict(market(), symbol="SOL")
        response = self.client.post("/research/coinbase/market-eligibility",
                                    headers={"Authorization": "Bearer " + TOKEN},
                                    json={"market": row})
        self.assertEqual(response.status_code, 400)
        provider.assert_not_called()
        with _LOCK:
            self.assertEqual(len(_REQUESTS), 0)
            self.assertEqual(len(_PROVIDER_RESERVATIONS), 0)


if __name__ == "__main__":
    unittest.main()
