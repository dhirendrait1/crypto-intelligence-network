"""Read-only shortlist API contract tests; router mounted only inside this test app."""
import unittest
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from cin_shortlist_scoring import WEIGHTS
from cin_shortlist_research_api import router


def make_candidate(symbol="BTC", score=80.0):
    timestamp = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    return {
        "symbol": symbol,
        "factors": {key: {"score": score, "source": "synthetic-test-fixture",
                           "observed_at": timestamp} for key in WEIGHTS},
        "gates": {"security_clear": True, "liquidity_sufficient": True,
                  "data_reliable": True, "risk_acceptable": True},
    }


class ResearchShortlistApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app = FastAPI()
        app.include_router(router)
        cls.client = TestClient(app)

    def post(self, candidates):
        return self.client.post("/research/shortlist/evaluate", json={"candidates": candidates})

    def test_valid_inputs_ranked_with_no_execution(self):
        response = self.post([make_candidate("ETH", 70.0), make_candidate("BTC", 85.0)])
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["execution_enabled"])
        self.assertEqual(payload["mode"], "caller_supplied_offline_research")
        self.assertEqual([x["symbol"] for x in payload["results"]], ["BTC", "ETH"])

    def test_missing_factor_not_scored(self):
        item = make_candidate()
        del item["factors"]["on_chain"]
        response = self.post([item])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"][0]["status"], "insufficient_data")
        self.assertIsNone(response.json()["results"][0]["score"])

    def test_security_override(self):
        item = make_candidate(score=100.0)
        item["gates"]["security_clear"] = False
        response = self.post([item])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"][0]["status"], "rejected")

    def test_duplicate_symbol_rejected(self):
        self.assertEqual(self.post([make_candidate(), make_candidate()]).status_code, 400)

    def test_future_timestamp_rejected(self):
        item = make_candidate()
        item["factors"]["technical"]["observed_at"] = (
            datetime.now(timezone.utc) + timedelta(hours=1)
        ).isoformat()
        self.assertEqual(self.post([item]).status_code, 400)

    def test_bad_gate_types_and_fields_rejected(self):
        item = make_candidate()
        item["gates"]["security_clear"] = "yes"
        self.assertEqual(self.post([item]).status_code, 422)
        item = make_candidate()
        item["factors"]["technical"]["unknown"] = 5
        self.assertEqual(self.post([item]).status_code, 422)

    def test_nonfinite_score_rejected(self):
        item = make_candidate()
        item["factors"]["technical"]["score"] = "NaN"
        self.assertEqual(self.post([item]).status_code, 422)

    def test_empty_request_is_nonexecuting(self):
        result = self.post([])
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["results"], [])


if __name__ == "__main__":
    unittest.main()
