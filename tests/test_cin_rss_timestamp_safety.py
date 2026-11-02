import io
import unittest
from unittest.mock import patch

import cin_public_news_sentiment_api as api
from cin_shortlist_news_evidence import news_evidence
from datetime import datetime, timezone
from email.utils import format_datetime


class RssTimestampSafetyTests(unittest.TestCase):
    def fetch(self, date):
        xml = (f"<rss><channel><item><title>Bitcoin update</title>"
               f"<link>https://example.test/story</link><pubDate>{date}</pubDate>"
               f"</item></channel></rss>").encode()
        with patch.object(api, "_RSS_FEEDS", (("CoinDesk public RSS", "https://example.test/rss"),)):
            with patch.object(api.urllib.request, "urlopen", side_effect=lambda *a, **k: io.BytesIO(xml)):
                return api._get_rss_articles("bitcoin", 10)

    def test_rss_without_timezone_is_not_accepted_for_news_evidence(self):
        now = datetime.now(timezone.utc)
        rows, source = self.fetch(format_datetime(now).rsplit(" ", 1)[0])
        self.assertEqual(rows[0]["provider_seen_at_validation_status"], "missing")
        with self.assertRaises(ValueError):
            news_evidence({"source": source, "query": "bitcoin", "articles": rows, "count": 1},
                          asset_id="bitcoin", now=now)

    def test_rss_with_timezone_can_be_preliminary(self):
        now = datetime.now(timezone.utc)
        rows, source = self.fetch(format_datetime(now))
        self.assertEqual(rows[0]["provider_seen_at_validation_status"], "valid")
        result = news_evidence({"source": source, "query": "bitcoin", "articles": rows, "count": 1},
                               asset_id="bitcoin", now=now)
        self.assertEqual(result["status"], "preliminary")
        self.assertEqual(result["timestamp_semantics"], "rss_feed_reported_date_not_independently_verified")
