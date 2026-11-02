import unittest
from datetime import datetime, timezone
from copy import deepcopy
from cin_shortlist_evidence_gate import evaluate

NOW = datetime(2026, 11, 2, 12, tzinfo=timezone.utc)

def good():
    entry = {"status": "available", "asset_id": "bitcoin", "source": "example",
             "source_url": "https://example.test/source", "observed_at": NOW.isoformat()}
    evidence = {key: dict(entry) for key in ("market", "chart", "news", "social", "market_sentiment")}
    evidence["market"]["price"] = 70000
    evidence["chart"].update(horizon="24h", closed_candles=True, coverage="complete")
    return {"asset_id": "bitcoin", "market_id": "BTC-USD", "evidence": evidence}

class EvidenceGateTests(unittest.TestCase):
    def test_complete_evidence_has_no_invented_forecast(self):
        result = evaluate([good()], "24h", NOW)
        self.assertEqual(len(result["eligible"]), 1)
        self.assertIsNone(result["eligible"][0]["probability"])
        self.assertEqual(result["ranking_status"], "not_assessed")

    def test_missing_social_excludes_candidate(self):
        candidate = good()
        del candidate["evidence"]["social"]
        result = evaluate([candidate], "24h", NOW)
        self.assertEqual(result["eligible"], [])
        self.assertIn("social: unavailable", result["excluded"][0]["reasons"])

    def test_stale_mismatched_and_incomplete_evidence_excludes(self):
        candidate = good()
        candidate["evidence"]["news"]["observed_at"] = "2026-01-01T00:00:00+00:00"
        candidate["evidence"]["social"]["asset_id"] = "ethereum"
        candidate["evidence"]["chart"]["closed_candles"] = False
        result = evaluate([candidate], "24h", NOW)
        self.assertEqual(result["eligible"], [])
        self.assertTrue(any("stale" in reason for reason in result["excluded"][0]["reasons"]))
        self.assertTrue(any("asset mismatch" in reason for reason in result["excluded"][0]["reasons"]))

    def test_does_not_treat_one_day_chart_as_seven_days(self):
        self.assertEqual(evaluate([good()], "7d", NOW)["eligible"], [])

    def test_duplicate_does_not_fill_shortlist(self):
        candidate = good()
        result = evaluate([candidate, deepcopy(candidate)], "24h", NOW)
        self.assertEqual(len(result["eligible"]), 1)

if __name__ == "__main__":
    unittest.main()

