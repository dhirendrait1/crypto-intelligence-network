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

    def test_conflicting_statuses_for_same_category_are_not_hidden(self):
        result = assess_growth_fundamentals(
            "ETH",
            [
                self.record(status="verified"),
                self.record(status="unverified", source_name="Second source"),
            ],
            now=self.now,
        )
        coverage = result["coverage"]["usage_and_adoption"]
        self.assertEqual(coverage["status"], "conflicting")
        self.assertTrue(coverage["conflict_detected"])
        self.assertEqual(result["overall_status"], "evidence_conflicting_or_incomplete")
        self.assertEqual(result["evidence_coverage_score"], 0)

    def test_non_object_record_is_retained_and_reported(self):
        result = assess_growth_fundamentals("ETH", ["not-a-record"], now=self.now)
        self.assertEqual(result["invalid_evidence_record_count"], 1)
        self.assertEqual(result["unrecognized_category_count"], 1)
        self.assertEqual(result["overall_status"], "evidence_invalid_or_incomplete")
        self.assertEqual(result["evidence"][0]["status"], "unverified")

    def test_unknown_category_prevents_complete_overall_status(self):
        records = [
            self.record(category=category)
            for category in (
                "usage_and_adoption", "fees_and_revenue", "token_utility",
                "tokenomics_and_unlocks", "security_and_audits",
                "developer_activity", "holder_concentration",
                "ecosystem_and_competition",
            )
        ]
        records.append(self.record(category="unrecognized_category"))
        result = assess_growth_fundamentals("ETH", records, now=self.now)
        self.assertEqual(result["verified_category_count"], 8)
        self.assertEqual(result["unrecognized_category_count"], 1)
        self.assertEqual(result["overall_status"], "evidence_invalid_or_incomplete")

    def test_credentials_in_source_url_do_not_support_verified_status(self):
        result = assess_growth_fundamentals(
            "ETH", [self.record(source_url="https://user:pass@example.com/report")], now=self.now
        )
        self.assertEqual(result["evidence"][0]["status"], "unverified")
        self.assertIn("source_url", result["evidence"][0]["missing_fields"])

    def test_duplicate_evidence_is_counted_once_in_category_coverage(self):
        first = self.record()
        second = self.record(source_url="https://example.com/report/")
        result = assess_growth_fundamentals("ETH", [first, second], now=self.now)
        coverage = result["coverage"]["usage_and_adoption"]
        self.assertEqual(coverage["evidence_count"], 1)
        self.assertEqual(coverage["duplicate_record_count"], 1)

    def test_invalid_freshness_threshold_falls_back_safely(self):
        result = assess_growth_fundamentals(
            "ETH", [self.record()], now=self.now, max_age_days=-1
        )
        self.assertFalse(result["freshness_threshold_valid"])
        self.assertEqual(result["freshness_threshold_days"], 90)

    def test_future_publication_has_no_nonnegative_age_claim(self):
        result = assess_growth_fundamentals(
            "ETH", [self.record(published_at="2026-10-25T00:00:00Z")], now=self.now
        )
        self.assertIsNone(result["evidence"][0]["publication_age_days"])
        self.assertEqual(
            result["evidence"][0]["timestamp_validation_errors"],
            ["published_at_is_in_the_future"],
        )

    def test_invalid_assessment_clock_falls_back_and_is_reported(self):
        result = assess_growth_fundamentals("ETH", [self.record()], now="not-a-datetime")
        self.assertFalse(result["assessment_clock_valid"])
        self.assertIn(result["evidence"][0]["status"], {"verified", "unverified"})

    def test_valid_http_url_is_accepted_as_metadata(self):
        result = assess_growth_fundamentals("ETH", [self.record(source_url="http://example.com/report")], now=self.now)
        self.assertEqual(result["evidence"][0]["status"], "verified")
        self.assertTrue(result["evidence"][0]["source_url_valid"])
        self.assertFalse(result["cin_independently_verified_claims"])

    def test_timezone_naive_assessment_clock_falls_back_and_is_reported(self):
        result = assess_growth_fundamentals(
            "ETH", [self.record()], now=self.now.replace(tzinfo=None)
        )
        self.assertFalse(result["assessment_clock_valid"])
        self.assertFalse(result["evidence"][0]["assessment_clock_valid"])


    def test_raw_whitespace_and_control_characters_in_source_urls_are_rejected(self):
        for url in (
            "https://example.com/report\\n.evil",
            "https://example.com/report\\t.evil",
            "https://example.com/report with-space",
        ):
            result = assess_growth_fundamentals(
                "ETH", [self.record(source_url=url)], now=self.now
            )
            self.assertFalse(result["evidence"][0]["source_url_valid"])
            self.assertEqual(result["evidence"][0]["status"], "unverified")
