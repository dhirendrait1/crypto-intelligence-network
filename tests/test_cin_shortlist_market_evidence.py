import unittest
from datetime import datetime, timedelta, timezone
from cin_shortlist_market_evidence import coinbase_market_evidence
from cin_shortlist_evidence_gate import evaluate

NOW = datetime(2026, 11, 2, 12, tzinfo=timezone.utc)
def sample():
    return {"source": "Coinbase Exchange public API", "currency": "USD", "count": 1,
            "data": [{"id": "bitcoin", "symbol": "BTC", "currency": "USD",
                      "product_id": "BTC-USD", "price": 70000, "last_updated": NOW.isoformat(),
                      "freshness_status": "fresh", "analysis_eligible": True}]}
class MarketEvidenceTests(unittest.TestCase):
    def call(self, payload, market="BTCUSD"):
        return coinbase_market_evidence(payload, asset_id="bitcoin", market_id=market, now=NOW)
    def test_exact_usd_market_is_attributed_to_ticker(self):
        item = self.call(sample())
        self.assertEqual(item["price"], 70000)
        self.assertEqual(item["market_id"], "BTCUSD")
        self.assertTrue(item["source_url"].endswith("/BTC-USD/ticker"))
    def test_market_alone_cannot_create_a_shortlist(self):
        candidate = {"asset_id": "bitcoin", "market_id": "BTCUSD",
                     "evidence": {"market": self.call(sample())}}
        result = evaluate([candidate], "24h", NOW)
        self.assertFalse(result["eligible"])
        self.assertIn("social: unavailable", result["excluded"][0]["reasons"])
        self.assertNotIn("market: identity mismatch", result["excluded"][0]["reasons"])
    def test_usdt_market_is_never_substituted(self):
        with self.assertRaises(ValueError): self.call(sample(), "BTCUSDT")
    def test_stale_future_and_unavailable_price_are_rejected(self):
        for value in ((NOW - timedelta(minutes=16)).isoformat(), (NOW + timedelta(seconds=1)).isoformat(), None):
            data=sample(); data["data"][0]["last_updated"]=value
            with self.subTest(value=value), self.assertRaises(ValueError): self.call(data)
        for value in (None, 0, float("nan"), True, 10**1000):
            data=sample(); data["data"][0]["price"]=value
            with self.subTest(value=str(value)[:10]), self.assertRaises(ValueError): self.call(data)
    def test_wrong_product_and_duplicate_are_rejected(self):
        data=sample(); data["data"][0]["product_id"]="ETH-USD"
        with self.assertRaises(ValueError): self.call(data)
        data=sample(); data["data"].append(dict(data["data"][0])); data["count"]=2
        with self.assertRaises(ValueError): self.call(data)

