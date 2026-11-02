import json
import unittest
import urllib.error
from datetime import datetime, timezone
from unittest.mock import patch
import cin_public_social_mastodon as social

NOW = datetime(2026, 11, 2, 12, tzinfo=timezone.utc)
class Response:
    def __init__(self, payload): self.payload = payload
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self, limit): return self.payload[:limit]

def post(**changes):
    item = {"id": "42", "visibility": "public", "created_at": NOW.isoformat(),
            "tags": [{"name": "Bitcoin"}], "content": "not retained"}
    item.update(changes)
    return item

class SocialTests(unittest.TestCase):
    def test_counts_only_unique_recent_public_matching_posts(self):
        posts = [post(), post(), post(id="43", visibility="private"),
                 post(id="44", tags=[{"name":"ethereum"}]),
                 post(id="45", created_at="2020-01-01T00:00:00Z")]
        with patch.object(social.urllib.request, "urlopen", return_value=Response(json.dumps(posts).encode())) as fetch:
            result = social.fetch_public_observations("bitcoin", NOW)
        self.assertEqual(result["recent_public_post_count"], 1)
        self.assertEqual(result["sentiment"], "not_assessed")
        self.assertNotIn("content", json.dumps(result))
        self.assertEqual(fetch.call_args.kwargs["timeout"], 8)

    def test_empty_feed_does_not_become_neutral_sentiment(self):
        with patch.object(social.urllib.request, "urlopen", return_value=Response(b"[]")):
            result = social.fetch_public_observations("ethereum", NOW)
        self.assertEqual(result["status"], "no_recent_observations")
        self.assertEqual(result["sentiment"], "not_assessed")
        self.assertIsNone(result["newest_post_at"])

    def test_rejects_unsupported_asset_and_oversized_data(self):
        with self.assertRaises(ValueError): social.fetch_public_observations("BTC/../../", NOW)
        with patch.object(social.urllib.request, "urlopen", return_value=Response(b"x" * (social.MAX_BYTES + 1))):
            with self.assertRaises(ValueError): social.fetch_public_observations("bitcoin", NOW)

    def test_401_is_not_a_successful_empty_feed(self):
        failure = urllib.error.HTTPError("https://mastodon.social", 401, "unauthorized", {}, None)
        with patch.object(social.urllib.request, "urlopen", side_effect=failure):
            with self.assertRaises(urllib.error.HTTPError): social.fetch_public_observations("bitcoin", NOW)

