"""HTTP contract tests for opt-in, unmounted CIN Coinbase research route."""
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from cin_coinbase_dashboard_research_api import router
from cin_coinbase_public_orderbook import PublicBookError
from cin_coinbase_staging_guard import _LOCK, _REQUESTS, _PROVIDER_RESERVATIONS


def market():
    return {
        "id": "bitcoin", "symbol": "BTC", "currency": "USD",
        "price": 100.5,
        "last_updated": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(),
        "freshness_status": "fresh", "analysis_eligible": True,
        "total_volume_24h": 12345.0,
    }


class CoinbaseDashboardResearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app = FastAPI()
        app.include_router(router)  # Staging-only explicit test registration
        cls.client = TestClient(app)

    def setUp(self):
        self.env = patch.dict("os.environ", {
            "CIN_COINBASE_RESEARCH_STAGE": "staging",
            "CIN_COINBASE_RESEARCH_TOKEN": "cin-internal-test-token-unique-0123456789abcdef",
        })
        self.env.start()
        self.addCleanup(self.env.stop)
        with _LOCK:
            _REQUESTS.clear()
            _PROVIDER_RESERVATIONS.clear()

    def post(self, url, **kwargs):
        return self.client.post(url, headers={
            "Authorization": "Bearer cin-internal-test-token-unique-0123456789abcdef",
        }, **kwargs)

    @patch.dict("os.environ", {"CIN_COINBASE_RESEARCH_ENABLED": ""})
    @patch("cin_coinbase_dashboard_research_api.research_liquidity_with_market_status")
    def test_off_by_default_never_calls_provider(self, worker):
        response = self.post("/research/coinbase/market-eligibility",
                                    json={"market": market()})
        self.assertEqual(response.status_code, 404)
        worker.assert_not_called()

    @patch.dict("os.environ", {"CIN_COINBASE_RESEARCH_ENABLED": "true"})
    @patch("cin_coinbase_dashboard_research_api.research_liquidity_with_market_status")
    def test_nonexact_feature_flag_never_activates(self, worker):
        self.assertEqual(self.post("/research/coinbase/market-eligibility",
                                         json={"market": market()}).status_code, 404)
        worker.assert_not_called()

    @patch.dict("os.environ", {"CIN_COINBASE_RESEARCH_ENABLED": "1"})
    @patch("cin_coinbase_dashboard_research_api.research_liquidity_with_market_status")
    def test_dashboard_safe_insufficient_data_response(self, worker):
        worker.return_value = {
            "eligibility_status": "insufficient_data", "execution_enabled": False,
            "product_status": "online", "book_requested": True,
            "reason": "Source provenance unresolved",
            "eligibility_evidence": {
                "data_reliable": True, "liquidity_sufficient": None,
                "security_clear": None, "risk_acceptable": None,
            },
            "diagnostics": {"bid_depth_quote": "1000000", "private": "no leak"},
        }
        response = self.post("/research/coinbase/market-eligibility",
                                    json={"market": market()})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["schema_version"], "cin-coinbase-market-eligibility-v1")
        self.assertEqual(body["status"], "insufficient_data")
        self.assertFalse(body["shortlist_approved"])
        self.assertFalse(body["execution_enabled"])
        self.assertNotIn("diagnostics", body)
        self.assertNotIn("1000000", response.text)
        worker.assert_called_once()

    @patch.dict("os.environ", {"CIN_COINBASE_RESEARCH_ENABLED": "1"})
    @patch("cin_coinbase_dashboard_research_api.research_liquidity_with_market_status")
    def test_inactive_product_is_rejected(self, worker):
        worker.return_value = {
            "status": "rejected", "product_status": "offline",
            "reason": "Coinbase product is not active",
            "book_requested": False, "execution_enabled": False,
        }
        response = self.post("/research/coinbase/market-eligibility",
                                    json={"market": market()})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "rejected")
        self.assertFalse(response.json()["book_requested"])

    @patch.dict("os.environ", {"CIN_COINBASE_RESEARCH_ENABLED": "1"})
    @patch("cin_coinbase_dashboard_research_api.research_liquidity_with_market_status")
    def test_provider_errors_are_redacted(self, worker):
        worker.side_effect = PublicBookError("sensitive network detail")
        response = self.post("/research/coinbase/market-eligibility",
                                    json={"market": market()})
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("sensitive", response.text)

    @patch.dict("os.environ", {"CIN_COINBASE_RESEARCH_ENABLED": "1"})
    @patch("cin_coinbase_dashboard_research_api.research_liquidity_with_market_status")
    def test_allowlist_rejects_unknown_pairs_before_network(self, worker):
        row = dict(market(), symbol="SOL")
        response = self.post("/research/coinbase/market-eligibility",
                                    json={"market": row})
        self.assertEqual(response.status_code, 400)
        worker.assert_not_called()

    @patch.dict("os.environ", {"CIN_COINBASE_RESEARCH_ENABLED": "1"})
    @patch("cin_coinbase_dashboard_research_api.research_liquidity_with_market_status")
    def test_reject_positive_gate_escalation(self, worker):
        worker.return_value = {
            "eligibility_status": "insufficient_data", "execution_enabled": False,
            "eligibility_evidence": {
                "liquidity_sufficient": True, "security_clear": None, "risk_acceptable": None,
            },
        }
        response = self.post("/research/coinbase/market-eligibility",
                                    json={"market": market()})
        self.assertEqual(response.status_code, 503)

    @patch.dict("os.environ", {"CIN_COINBASE_RESEARCH_ENABLED": "1"})
    @patch("cin_coinbase_dashboard_research_api.research_liquidity_with_market_status")
    def test_malformed_input_is_422_before_network(self, worker):
        row = dict(market(), price=-1.0)
        response = self.post("/research/coinbase/market-eligibility",
                                    json={"market": row})
        self.assertEqual(response.status_code, 422)
        worker.assert_not_called()


if __name__ == "__main__":
    unittest.main()
