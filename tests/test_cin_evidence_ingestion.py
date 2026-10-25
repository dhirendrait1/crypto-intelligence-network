import json
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from cin_evidence_ingestion import (
    EvidenceSourceError,
    fetch_github_repository_evidence,
)


class FakeResponse:
    status = 200

    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, limit=-1):
        return json.dumps(self.payload).encode("utf-8")


class InvalidUtf8Response(FakeResponse):
    def read(self, limit=-1):
        return bytes([255, 254])


class EvidenceIngestionTests(unittest.TestCase):
    @patch("cin_evidence_ingestion.urlopen")
    def test_normalizes_allowlisted_repo_and_never_verifies_claim(self, mocked):
        mocked.return_value = FakeResponse({
            "full_name": "ethereum/go-ethereum",
            "default_branch": "master",
            "pushed_at": "2026-10-20T10:00:00Z",
            "updated_at": "2026-10-21T10:00:00Z",
            "stargazers_count": 50000,
            "forks_count": 20000,
            "open_issues_count": 1000,
            "archived": False,
        })
        result = fetch_github_repository_evidence()
        self.assertEqual(result["symbol"], "ETH")
        self.assertEqual(result["category"], "developer_activity")
        self.assertEqual(result["retrieval_status"], "success")
        self.assertEqual(result["claim_verification_status"], "unverified")
        self.assertFalse(result["independently_verified"])
        self.assertIn("retrieved_at", result)
        self.assertIn("published_at", result)


    @patch("cin_evidence_ingestion.urlopen")
    def test_invalid_utf8_response_is_controlled_source_error(self, mocked):
        mocked.return_value = InvalidUtf8Response({})
        with self.assertRaisesRegex(EvidenceSourceError, "UnicodeDecodeError"):
            fetch_github_repository_evidence()

    def test_rejects_arbitrary_repository(self):
        with self.assertRaises(ValueError):
            fetch_github_repository_evidence("attacker/arbitrary")

    def test_rejects_unbounded_timeout(self):
        with self.assertRaises(ValueError):
            fetch_github_repository_evidence(timeout=60)

    def test_rejects_boolean_or_fractional_timeout(self):
        for timeout in (True, False, 1.5, "8"):
            with self.subTest(timeout=timeout):
                with self.assertRaises(ValueError):
                    fetch_github_repository_evidence(timeout=timeout)

    @patch("cin_evidence_ingestion.urlopen", side_effect=TimeoutError())
    def test_timeout_is_reported_as_source_error(self, mocked):
        with self.assertRaises(EvidenceSourceError):
            fetch_github_repository_evidence()

    @patch("cin_evidence_ingestion.urlopen")
    def test_mismatched_payload_is_rejected(self, mocked):
        mocked.return_value = FakeResponse({"full_name": "someone/else"})
        with self.assertRaises(EvidenceSourceError):
            fetch_github_repository_evidence()


    @patch("cin_evidence_ingestion.urlopen")
    def test_non_string_repository_identity_is_controlled_source_error(self, mocked):
        mocked.return_value = FakeResponse({"full_name": None})
        with self.assertRaisesRegex(EvidenceSourceError, "did not match"):
            fetch_github_repository_evidence()

    @patch("cin_evidence_ingestion.urlopen")
    def test_non_object_json_payload_is_controlled_source_error(self, mocked):
        mocked.return_value = FakeResponse(["not", "an", "object"])
        with self.assertRaisesRegex(EvidenceSourceError, "JSON object"):
            fetch_github_repository_evidence()

    @patch("cin_evidence_ingestion.urlopen")
    def test_negative_or_boolean_counter_is_rejected(self, mocked):
        mocked.return_value = FakeResponse({
            "full_name": "ethereum/go-ethereum",
            "default_branch": "master",
            "pushed_at": "2026-10-20T10:00:00Z",
            "updated_at": "2026-10-21T10:00:00Z",
            "stargazers_count": True,
            "forks_count": 20,
            "open_issues_count": -1,
            "archived": False,
        })
        with self.assertRaisesRegex(EvidenceSourceError, "stargazers_count"):
            fetch_github_repository_evidence()

    @patch("cin_evidence_ingestion.urlopen")
    def test_malformed_or_timezone_naive_timestamp_is_rejected(self, mocked):
        base = {
            "full_name": "ethereum/go-ethereum",
            "default_branch": "master",
            "pushed_at": "not-a-timestamp",
            "updated_at": "2026-10-21T10:00:00",
            "stargazers_count": 50,
            "forks_count": 20,
            "open_issues_count": 1,
            "archived": False,
        }
        mocked.return_value = FakeResponse(base)
        with self.assertRaisesRegex(EvidenceSourceError, "pushed_at"):
            fetch_github_repository_evidence()

    @patch("cin_evidence_ingestion.urlopen")
    def test_missing_optional_metadata_is_reported_as_partial(self, mocked):
        mocked.return_value = FakeResponse({
            "full_name": "ethereum/go-ethereum",
            "default_branch": "master",
            "pushed_at": "2026-10-20T10:00:00Z",
            "updated_at": "2026-10-21T10:00:00Z",
            "archived": False,
        })
        result = fetch_github_repository_evidence()
        self.assertEqual(result["validation_status"], "metadata_partial")
        self.assertIn("stargazers_count", result["missing_fields"])


    @patch("cin_evidence_ingestion.urlopen")
    def test_recent_repository_timestamp_is_fresh(self, mocked):
        mocked.return_value = FakeResponse({
            "full_name": "ethereum/go-ethereum",
            "default_branch": "master",
            "pushed_at": "2026-10-23T10:00:00Z",
            "updated_at": "2026-10-23T10:00:00Z",
            "stargazers_count": 50000,
            "forks_count": 20000,
            "open_issues_count": 1000,
            "archived": False,
        })
        result = fetch_github_repository_evidence()
        self.assertEqual(result["freshness_status"], "fresh")
        self.assertIsInstance(result["freshness_age_seconds"], int)
        self.assertIn("7 days", result["freshness_policy"])

    @patch("cin_evidence_ingestion.urlopen")
    def test_old_repository_timestamp_is_stale(self, mocked):
        mocked.return_value = FakeResponse({
            "full_name": "ethereum/go-ethereum",
            "default_branch": "master",
            "pushed_at": "2020-01-01T00:00:00Z",
            "updated_at": "2020-01-02T00:00:00Z",
            "stargazers_count": 50000,
            "forks_count": 20000,
            "open_issues_count": 1000,
            "archived": False,
        })
        result = fetch_github_repository_evidence()
        self.assertEqual(result["freshness_status"], "stale")
        self.assertGreater(result["freshness_age_seconds"], 7 * 24 * 60 * 60)

    @patch("cin_evidence_ingestion.urlopen")
    def test_missing_repository_timestamps_have_unknown_freshness(self, mocked):
        mocked.return_value = FakeResponse({
            "full_name": "ethereum/go-ethereum",
            "default_branch": "master",
            "stargazers_count": 50000,
            "forks_count": 20000,
            "open_issues_count": 1000,
            "archived": False,
        })
        result = fetch_github_repository_evidence()
        self.assertEqual(result["freshness_status"], "unknown")
        self.assertIsNone(result["freshness_age_seconds"])

    @patch("cin_evidence_ingestion.urlopen")
    def test_future_repository_timestamp_is_rejected(self, mocked):
        future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        mocked.return_value = FakeResponse({
            "full_name": "ethereum/go-ethereum",
            "default_branch": "master",
            "pushed_at": future,
            "updated_at": "2026-10-21T10:00:00Z",
            "stargazers_count": 50000,
            "forks_count": 20000,
            "open_issues_count": 1000,
            "archived": False,
        })
        with self.assertRaisesRegex(EvidenceSourceError, "pushed_at"):
            fetch_github_repository_evidence()


    @patch("cin_evidence_ingestion.urlopen")
    def test_oversized_provider_response_is_rejected_before_json_parse(self, mocked):
        class OversizedResponse(FakeResponse):
            def read(self, limit=-1):
                self.requested_limit = limit
                return b"x" * limit

        response = OversizedResponse({})
        mocked.return_value = response
        with self.assertRaisesRegex(EvidenceSourceError, "exceeded the configured size limit"):
            fetch_github_repository_evidence()
        self.assertEqual(response.requested_limit, 1_000_001)

    @patch("cin_evidence_ingestion.urlopen")
    def test_provider_timestamp_strings_are_bounded_and_control_free(self, mocked):
        base = {
            "full_name": "ethereum/go-ethereum",
            "default_branch": "main",
            "pushed_at": "2026-10-23T10:00:00Z",
            "updated_at": "2026-10-23T10:00:00Z",
            "stargazers_count": 50,
            "forks_count": 20,
            "open_issues_count": 1,
            "archived": False,
        }
        for bad_timestamp in ("x" * 65, "2026-10-23T10:00:00Z\\n"):
            with self.subTest(timestamp_length=len(bad_timestamp)):
                payload = dict(base, pushed_at=bad_timestamp)
                mocked.return_value = FakeResponse(payload)
                with self.assertRaisesRegex(EvidenceSourceError, "pushed_at"):
                    fetch_github_repository_evidence()

    @patch("cin_evidence_ingestion.urlopen")
    def test_default_branch_metadata_is_bounded_and_control_free(self, mocked):
        base = {
            "full_name": "ethereum/go-ethereum",
            "default_branch": "main",
            "pushed_at": "2026-10-23T10:00:00Z",
            "updated_at": "2026-10-23T10:00:00Z",
            "stargazers_count": 50,
            "forks_count": 20,
            "open_issues_count": 1,
            "archived": False,
        }
        for bad_branch in ("x" * 256, "main\tbranch"):
            with self.subTest(branch_length=len(bad_branch)):
                mocked.return_value = FakeResponse(dict(base, default_branch=bad_branch))
                with self.assertRaisesRegex(EvidenceSourceError, "default_branch"):
                    fetch_github_repository_evidence()

if __name__ == "__main__":
    unittest.main()
