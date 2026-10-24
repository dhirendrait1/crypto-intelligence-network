import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from cin_evidence_ingestion import (
    EvidenceSourceError,
    _freshness_status,
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


class FakeInvalidUtf8Response(FakeResponse):
    def read(self, limit=-1):
        return b"\xff\xfe"


class FakeRawResponse(FakeResponse):
    def __init__(self, raw, status=200):
        self.raw = raw
        self.status = status

    def read(self, limit=-1):
        return self.raw[:limit]


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
        self.assertEqual(result["source_timestamp_field"], "pushed_at")
        self.assertEqual(result["source_timestamp"], "2026-10-20T10:00:00Z")
        self.assertEqual(result["timestamp_semantics"], "repository_activity_not_publication")
        self.assertEqual(result["metadata_completeness"], "complete")
        self.assertEqual(result["metadata_missing_fields"], [])

    def test_rejects_arbitrary_repository(self):
        with self.assertRaises(ValueError):
            fetch_github_repository_evidence("attacker/arbitrary")

    def test_rejects_invalid_timeout_types_and_bounds(self):
        for timeout in (0, 16, 60, True, 2.5, "8", None):
            with self.subTest(timeout=timeout):
                with self.assertRaises(ValueError):
                    fetch_github_repository_evidence(timeout=timeout)

    @patch("cin_evidence_ingestion.urlopen", side_effect=TimeoutError())
    def test_timeout_is_reported_as_source_error(self, mocked):
        with self.assertRaises(EvidenceSourceError):
            fetch_github_repository_evidence()

    @patch("cin_evidence_ingestion.urlopen")
    def test_non_200_response_status_is_rejected(self, mocked):
        mocked.return_value = FakeRawResponse(b'{"full_name":"ethereum/go-ethereum"}', status=503)
        with self.assertRaisesRegex(EvidenceSourceError, "HTTP 503"):
            fetch_github_repository_evidence()

    @patch("cin_evidence_ingestion.urlopen")
    def test_http_error_is_reported_as_source_error(self, mocked):
        mocked.side_effect = HTTPError(
            "https://api.github.com/repos/ethereum/go-ethereum",
            503,
            "Service Unavailable",
            hdrs=None,
            fp=None,
        )
        with self.assertRaisesRegex(EvidenceSourceError, "HTTP 503"):
            fetch_github_repository_evidence()

    @patch("cin_evidence_ingestion.urlopen", side_effect=URLError("connection refused"))
    def test_url_error_is_reported_as_source_error(self, mocked):
        with self.assertRaisesRegex(EvidenceSourceError, "URLError"):
            fetch_github_repository_evidence()

    @patch("cin_evidence_ingestion.urlopen")
    def test_malformed_json_is_reported_as_source_error(self, mocked):
        mocked.return_value = FakeRawResponse(b'{"full_name":')
        with self.assertRaisesRegex(EvidenceSourceError, "JSONDecodeError"):
            fetch_github_repository_evidence()

    @patch("cin_evidence_ingestion.urlopen")
    def test_oversized_response_is_rejected_before_json_parsing(self, mocked):
        from cin_evidence_ingestion import MAX_RESPONSE_BYTES

        mocked.return_value = FakeRawResponse(b" " * (MAX_RESPONSE_BYTES + 1))
        with self.assertRaisesRegex(EvidenceSourceError, "exceeded the 1 MB size limit"):
            fetch_github_repository_evidence()

    @patch("cin_evidence_ingestion.urlopen")
    def test_invalid_utf8_is_reported_as_source_error(self, mocked):
        mocked.return_value = FakeInvalidUtf8Response({})
        with self.assertRaisesRegex(EvidenceSourceError, "UnicodeDecodeError"):
            fetch_github_repository_evidence()

    @patch("cin_evidence_ingestion.urlopen")
    def test_mismatched_payload_is_rejected(self, mocked):
        mocked.return_value = FakeResponse({"full_name": "someone/else"})
        with self.assertRaises(EvidenceSourceError):
            fetch_github_repository_evidence()

    @patch("cin_evidence_ingestion.urlopen")
    def test_non_object_json_payloads_raise_source_error(self, mocked):
        for payload in ([], "unexpected", 42, None):
            with self.subTest(payload=payload):
                mocked.return_value = FakeResponse(payload)
                with self.assertRaisesRegex(EvidenceSourceError, "JSON object"):
                    fetch_github_repository_evidence()

    @patch("cin_evidence_ingestion.urlopen")
    def test_null_optional_metadata_is_reported_as_partial(self, mocked):
        mocked.return_value = FakeResponse({
            "full_name": "ethereum/go-ethereum",
            "default_branch": None,
            "pushed_at": None,
            "updated_at": None,
            "stargazers_count": None,
            "forks_count": None,
            "open_issues_count": None,
            "archived": None,
        })
        result = fetch_github_repository_evidence()
        self.assertEqual(result["metadata_completeness"], "partial")
        self.assertEqual(result["metadata_missing_fields"], [
            "default_branch", "pushed_at", "updated_at", "stargazers_count",
            "forks_count", "open_issues_count", "archived",
        ])
        self.assertEqual(result["freshness_status"], "unknown")
        self.assertIsNone(result["source_timestamp_field"])
        self.assertEqual(result["claim_verification_status"], "unverified")
        self.assertFalse(result["independently_verified"])

    def test_freshness_uses_updated_at_when_pushed_at_is_missing(self):
        from datetime import datetime, timezone

        now = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)
        self.assertEqual(
            _freshness_status({"updated_at": "2026-10-24T12:00:00Z"}, now=now),
            "fresh",
        )
        self.assertEqual(
            _freshness_status({"updated_at": "2026-10-01T12:00:00Z"}, now=now),
            "stale",
        )

    @patch("cin_evidence_ingestion.urlopen")
    def test_malformed_repository_identity_raises_source_error(self, mocked):
        for full_name in (None, 42, [], {}):
            with self.subTest(full_name=full_name):
                mocked.return_value = FakeResponse({"full_name": full_name})
                with self.assertRaises(EvidenceSourceError):
                    fetch_github_repository_evidence()

    @patch("cin_evidence_ingestion.urlopen")
    def test_malformed_metadata_fields_raise_source_error(self, mocked):
        valid = {
            "full_name": "ethereum/go-ethereum",
            "default_branch": "master",
            "pushed_at": "2026-10-20T10:00:00Z",
            "updated_at": "2026-10-21T10:00:00Z",
            "stargazers_count": 10,
            "forks_count": 2,
            "open_issues_count": 3,
            "archived": False,
        }
        invalid_fields = {
            "default_branch": 12,
            "pushed_at": "not-a-timestamp",
            "updated_at": 123,
            "stargazers_count": -1,
            "forks_count": True,
            "open_issues_count": "3",
            "archived": "false",
        }
        for field, invalid_value in invalid_fields.items():
            with self.subTest(field=field, invalid_value=invalid_value):
                payload = {**valid, field: invalid_value}
                mocked.return_value = FakeResponse(payload)
                with self.assertRaises(EvidenceSourceError):
                    fetch_github_repository_evidence()

    @patch("cin_evidence_ingestion.urlopen")
    def test_timestamp_without_timezone_is_rejected(self, mocked):
        mocked.return_value = FakeResponse({
            "full_name": "ethereum/go-ethereum",
            "pushed_at": "2026-10-20T10:00:00",
        })
        with self.assertRaises(EvidenceSourceError):
            fetch_github_repository_evidence()

    @patch("cin_evidence_ingestion.urlopen")
    def test_partial_metadata_is_flagged_and_updated_timestamp_provenance_is_explicit(self, mocked):
        mocked.return_value = FakeResponse({
            "full_name": "ethereum/go-ethereum",
            "updated_at": "2026-10-24T10:00:00Z",
        })
        result = fetch_github_repository_evidence()
        self.assertEqual(result["metadata_completeness"], "partial")
        self.assertEqual(result["metadata_missing_fields"], [
            "default_branch", "pushed_at", "stargazers_count", "forks_count",
            "open_issues_count", "archived",
        ])
        self.assertEqual(result["source_timestamp_field"], "updated_at")
        self.assertEqual(result["published_at"], "2026-10-24T10:00:00Z")
        self.assertEqual(result["source_timestamp"], "2026-10-24T10:00:00Z")
        self.assertEqual(result["timestamp_semantics"], "repository_activity_not_publication")
        self.assertEqual(result["claim_verification_status"], "unverified")
        self.assertFalse(result["independently_verified"])

    def test_freshness_classification_boundaries_are_deterministic(self):
        from datetime import datetime, timezone, timedelta

        now = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)
        cases = (
            ({"pushed_at": (now - timedelta(days=2)).isoformat()}, "fresh"),
            ({"pushed_at": (now - timedelta(days=7)).isoformat()}, "fresh"),
            ({"pushed_at": (now - timedelta(days=7, seconds=1)).isoformat()}, "stale"),
            ({"pushed_at": (now + timedelta(minutes=1)).isoformat()}, "unknown"),
            ({}, "unknown"),
        )
        for payload, expected in cases:
            with self.subTest(payload=payload, expected=expected):
                self.assertEqual(_freshness_status(payload, now=now), expected)



if __name__ == "__main__":
    unittest.main()
