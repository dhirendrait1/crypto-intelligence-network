import unittest
from datetime import datetime, timezone
from copy import deepcopy
from cin_shortlist_chart_evidence import chart_evidence
from cin_shortlist_evidence_gate import evaluate

NOW = datetime(2026, 11, 2, 12, tzinfo=timezone.utc)

def payload(count=24, duration=3_600_000, timeframe="1h"):
    end = int(NOW.timestamp() * 1000)
    rows = []
    for i in range(count):
        start = end - (count - i) * duration
        rows.append({"open_time": start, "close_time": start + duration - 1,
                     "open": 100, "high": 103, "low": 99, "close": 102, "is_closed": True})
    return {"symbol": "BTCUSD", "timeframe": timeframe, "pair_metadata_status": "identified",
            "quote_currency": "USD", "source": "Example provider", "source_endpoint": "https://example.test",
            "count": len(rows), "data": rows}

class ChartTests(unittest.TestCase):
    def call(self, data, horizon="24h"):
        return chart_evidence(data, asset_id="bitcoin", market_id="BTCUSD", horizon=horizon, now=NOW)

    def test_complete_24h_and_7d(self):
        self.assertEqual(self.call(payload())["candle_count"], 24)
        self.assertEqual(self.call(payload(42, 14_400_000, "4h"), "7d")["candle_count"], 42)

    def test_realistic_response_maps_to_gate_without_inventing_other_sources(self):
        candidate = {"asset_id": "bitcoin", "market_id": "BTCUSD",
                     "evidence": {"chart": self.call(payload())}}
        result = evaluate([candidate], "24h", NOW)
        self.assertFalse(result["eligible"])
        reasons = result["excluded"][0]["reasons"]
        self.assertIn("social: unavailable", reasons)
        self.assertIn("news: unavailable", reasons)
        self.assertNotIn("chart: invalid or incomplete time window", reasons)

    def test_missing_candle_cannot_be_complete(self):
        data = payload(25)
        del data["data"][10]
        data["count"] -= 1
        with self.assertRaisesRegex(ValueError, "gap"): self.call(data)

    def test_incorrect_market_is_rejected(self):
        data = payload()
        data["symbol"] = "BTCUSDT"
        with self.assertRaisesRegex(ValueError, "market"): self.call(data)

    def test_quote_mismatch_is_rejected(self):
        data = payload()
        data["pair_metadata_status"] = "quote_mismatch"
        with self.assertRaisesRegex(ValueError, "quote"): self.call(data)

    def test_future_candle_cannot_be_claimed_closed(self):
        data = payload()
        data["data"][-1]["close_time"] += 3_600_000
        with self.assertRaises(ValueError): self.call(data)

    def test_duplicate_candle_is_rejected(self):
        data = payload()
        data["data"][1] = deepcopy(data["data"][0])
        with self.assertRaisesRegex(ValueError, "unordered"): self.call(data)

    def test_invalid_prices_rejected(self):
        data = payload()
        data["data"][-1]["close"] = float("nan")
        with self.assertRaisesRegex(ValueError, "price"): self.call(data)

if __name__ == "__main__": unittest.main()

