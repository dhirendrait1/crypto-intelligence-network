import unittest
from copy import deepcopy
from datetime import datetime, timezone
from cin_shortlist_social_evidence import social_evidence
from cin_shortlist_evidence_gate import evaluate

NOW = datetime(2026, 11, 2, 12, tzinfo=timezone.utc)
def good():
    return {"asset_id": "bitcoin", "source": "Mastodon public hashtag timeline",
            "source_url": "https://mastodon.social/api/v1/timelines/tag/bitcoin?limit=20",
            "status": "observations_available", "recent_public_post_count": 3,
            "newest_post_at": NOW.isoformat(),
            "sentiment": {"label": "positive", "confidence": "low", "classified_posts": 2,
                          "counts": {"positive": 2, "negative": 0, "mixed": 0, "unclassified": 1}}}
class SocialEvidenceTests(unittest.TestCase):
    def call(self, value): return social_evidence(value, asset_id="bitcoin", now=NOW)
    def test_valid_signal_remains_low_confidence(self):
        result = self.call(good())
        self.assertEqual(result["signal"], "positive")
        self.assertEqual(result["confidence"], "low")
    def test_unavailable_and_empty_are_not_neutral(self):
        for changes in ({"status": "no_recent_observations"}, {"recent_public_post_count": 0}):
            data = good(); data.update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError): self.call(data)
    def test_wrong_asset_source_and_stale_time_fail_closed(self):
        for changes in ({"asset_id": "ethereum"}, {"source_url": "https://other.example/"},
                        {"newest_post_at": "2020-01-01T00:00:00Z"}):
            data = good(); data.update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError): self.call(data)
    def test_inconsistent_counts_or_label_are_rejected(self):
        data = good(); data["sentiment"]["label"] = "negative"
        with self.assertRaises(ValueError): self.call(data)
        data = good(); data["sentiment"]["counts"]["positive"] = 10
        with self.assertRaises(ValueError): self.call(data)
    def test_social_alone_does_not_satisfy_other_mandatory_sources(self):
        candidate = {"asset_id": "bitcoin", "market_id": "BTCUSDT",
                     "evidence": {"social": self.call(good())}}
        result = evaluate([candidate], "24h", NOW)
        self.assertFalse(result["eligible"])
        self.assertIn("news: unavailable", result["excluded"][0]["reasons"])
        self.assertIn("market_sentiment: unavailable", result["excluded"][0]["reasons"])

