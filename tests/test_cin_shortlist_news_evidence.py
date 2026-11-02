import unittest
from datetime import datetime, timezone
from cin_shortlist_news_evidence import news_evidence

NOW = datetime(2026, 11, 2, 12, tzinfo=timezone.utc)
def article(title="Bitcoin network update", stamp=None, url="https://news.example/story"):
    return {"title": title, "url": url, "provider_seen_at_utc": stamp or NOW.isoformat(),
            "provider_seen_at_validation_status": "valid"}
def payload(rows=None):
    rows = [article()] if rows is None else rows
    return {"query": "bitcoin", "source": "GDELT DOC 2.0 public article search", "articles": rows, "count": len(rows)}
class NewsEvidenceTests(unittest.TestCase):
    def call(self, value): return news_evidence(value, asset_id="bitcoin", now=NOW)
    def test_recent_explicit_mention_and_timestamp(self):
        result = self.call(payload())
        self.assertEqual(result["status"], "preliminary")
        self.assertEqual(result["timestamp_semantics"], "provider_seen_at_not_verified_publication_time")
    def test_wrong_asset_or_unrelated_title_cannot_qualify(self):
        value=payload(); value["query"]="ethereum"
        with self.assertRaises(ValueError): self.call(value)
        with self.assertRaises(ValueError): self.call(payload([article(title="Ethereum rises")]))
    def test_stale_future_or_invalid_timestamp_cannot_qualify(self):
        for stamp in ("2020-01-01T00:00:00Z", "2030-01-01T00:00:00Z", "not-a-date", "2026-11-02T11:00:00"):
            with self.subTest(stamp=stamp), self.assertRaises(ValueError):
                self.call(payload([article(stamp=stamp)]))
    def test_rejects_bad_url_and_bad_provider_status(self):
        with self.assertRaises(ValueError):
            self.call(payload([article(url="https://user:password@example.test/")]))
        row=article(); row["provider_seen_at_validation_status"]="missing"
        with self.assertRaises(ValueError): self.call(payload([row]))
    def test_does_not_assign_headline_sentiment_or_forecast(self):
        value=self.call(payload())
        self.assertNotIn("sentiment", value)
        self.assertNotIn("probability", value)

    def test_rss_timestamp_provenance_is_not_assumed(self):
        value = payload(); value["source"] = "Public RSS"
        with self.assertRaises(ValueError): self.call(value)

