"""Tests for the pure GitHub connector-to-evidence mapping boundary."""
import unittest

from cin_github_evidence_mapping import build_github_evidence_snapshot


class GitHubEvidenceMappingTests(unittest.TestCase):
    def setUp(self):
        self.result = {
            "symbol": "ETH",
            "category": "developer_activity",
            "metric": "public_repository_activity_metadata",
            "source_name": "GitHub public repository API",
            "source_url": "https://api.github.com/repos/ethereum/go-ethereum",
            "repository": "ethereum/go-ethereum",
            "published_at": "2026-10-29T18:30:00+05:30",
            "retrieved_at": "2026-10-30T12:00:00Z",
            "value": {"stargazers_count": 50000, "forks_count": 20000},
            "retrieval_status": "success",
            "validation_status": "metadata_shape_validated",
            "freshness_status": "fresh",
            "claim_verification_status": "unverified",
            "independently_verified": False,
            "provenance": "public GitHub REST API; allowlisted repository",
            "limitations": ["Metadata does not establish investment merit."],
        }

    def test_maps_successful_result_to_narrow_context_only_snapshot(self):
        mapped = build_github_evidence_snapshot(self.result)
        self.assertEqual(mapped["source_namespace"], "github_public_repository_api")
        self.assertEqual(mapped["external_evidence_id"], "ethereum/go-ethereum")
        self.assertEqual(mapped["evidence_type"], "public_repository_metadata_snapshot")
        self.assertEqual(mapped["observed_at"], self.result["retrieved_at"])
        self.assertEqual(mapped["retrieved_at"], self.result["retrieved_at"])
        self.assertEqual(mapped["published_at"], "2026-10-29T18:30:00+05:30")
        self.assertEqual(mapped["metadata"], self.result)
        self.assertEqual(mapped["source_status"], "cin_retrieved")
        self.assertEqual(mapped["claim"]["predicate"], "public_metadata_snapshot_retrieved")
        self.assertEqual(mapped["claim"]["claim_status"], "not_assessed")
        self.assertEqual(mapped["claim"]["value"]["claim_verification_status"], "unverified")
        self.assertEqual(mapped["relationship"]["relationship"], "context_only")
        self.assertEqual(mapped["relationship"]["review_status"], "automated_candidate")

    def test_rejects_failed_retrieval_before_returning_persistence_arguments(self):
        failed = dict(self.result, retrieval_status="unavailable")
        with self.assertRaisesRegex(ValueError, "only successful"):
            build_github_evidence_snapshot(failed)

    def test_rejects_non_allowlisted_repository(self):
        invalid = dict(self.result, repository="attacker/other")
        with self.assertRaisesRegex(ValueError, "allowlist"):
            build_github_evidence_snapshot(invalid)

    def test_rejects_verification_promotion(self):
        invalid = dict(self.result, independently_verified=True)
        with self.assertRaisesRegex(ValueError, "unverified"):
            build_github_evidence_snapshot(invalid)

    def test_rejects_naive_retrieval_timestamp(self):
        invalid = dict(self.result, retrieved_at="2026-10-30T12:00:00")
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            build_github_evidence_snapshot(invalid)

    def test_omits_published_at_when_provider_has_no_timestamp(self):
        without_published = dict(self.result, published_at=None)
        mapped = build_github_evidence_snapshot(without_published)
        self.assertNotIn("published_at", mapped)


if __name__ == "__main__":
    unittest.main()
