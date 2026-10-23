import json
import unittest
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

    def test_rejects_arbitrary_repository(self):
        with self.assertRaises(ValueError):
            fetch_github_repository_evidence("attacker/arbitrary")

    def test_rejects_unbounded_timeout(self):
        with self.assertRaises(ValueError):
            fetch_github_repository_evidence(timeout=60)

    @patch("cin_evidence_ingestion.urlopen", side_effect=TimeoutError())
    def test_timeout_is_reported_as_source_error(self, mocked):
        with self.assertRaises(EvidenceSourceError):
            fetch_github_repository_evidence()

    @patch("cin_evidence_ingestion.urlopen")
    def test_mismatched_payload_is_rejected(self, mocked):
        mocked.return_value = FakeResponse({"full_name": "someone/else"})
        with self.assertRaises(EvidenceSourceError):
            fetch_github_repository_evidence()


if __name__ == "__main__":
    unittest.main()
