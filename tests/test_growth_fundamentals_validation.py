from datetime import datetime, timezone
import unittest

from growth_fundamentals_assessment import assess_growth_fundamentals


class GrowthFundamentalsValidationTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 24, tzinfo=timezone.utc)

    def record(self, **overrides):
        item = {
            "category": "usage_and_adoption",
            "source_name": "Example source",
            "source_url": "https://example.com/report",
            "published_at": "2026-10-01T00:00:00Z",
            "status": "verified",
        }
        item.update(overrides)
        return item

    def test_scheme_only_url_does_not_support_verified_status(self):
        result = assess_growth_fundamentals("ETH", [self.record(source_url="https://")], now=self.now)
        self.assertEqual(result["evidence"][0]["status"], "unverified")

    def test_url_without_hostname_does_not_support_verified_status(self):
        result = assess_growth_fundamentals("ETH", [self.record(source_url="http:///report")], now=self.now)
        self.assertEqual(result["evidence"][0]["status"], "unverified")

    def test_future_publication_timestamp_downgrades_verified_status(self):
        result = assess_growth_fundamentals(
            "ETH",
            [self.record(published_at="2026-10-25T00:00:00Z")],
            now=self.now,
        )
        self.assertEqual(result["evidence"][0]["status"], "unverified")
        self.assertFalse(result["cin_independently_verified_claims"])

    def test_timezone_naive_publication_timestamp_downgrades_verified_status(self):
        result = assess_growth_fundamentals(
            "ETH",
            [self.record(published_at="2026-10-01T00:00:00")],
            now=self.now,
        )
        self.assertEqual(result["evidence"][0]["status"], "unverified")
        self.assertIn("published_at", result["evidence"][0]["missing_fields"])

    def test_valid_http_url_is_accepted_as_metadata(self):
        result = assess_growth_fundamentals("ETH", [self.record(source_url="http://example.com/report")], now=self.now)
        self.assertEqual(result["evidence"][0]["status"], "verified")
        self.assertFalse(result["cin_independently_verified_claims"])
