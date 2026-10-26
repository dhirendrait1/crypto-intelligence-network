"""HTTP-level regression tests for the public evidence API."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

# Exercise the same patched scaffold application that CI validates for deployment.
CIN_DIR = Path(__file__).resolve().parents[1] / "cin"
sys.path.insert(0, str(CIN_DIR))

from app.main import app
from app import cin_evidence_ingestion_api as api
from app.cin_evidence_ingestion import EvidenceSourceError

client = TestClient(app)


class PublicEvidenceHttpTests(unittest.TestCase):
    def test_success_returns_http_200_and_unverified_evidence(self):
        evidence = {
            "symbol": "ETH",
            "retrieval_status": "success",
            "claim_verification_status": "unverified",
            "independently_verified": False,
            "source_timestamp": "2026-10-20T10:00:00Z",
            "source_timestamp_field": "pushed_at",
            "timestamp_semantics": "repository_metadata_timestamp_not_publication",
            "published_at": "2026-10-20T10:00:00Z",
        }
        with patch.object(api, "fetch_github_repository_evidence", return_value=evidence):
            response = client.post("/public-evidence-ingestion", json={})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), evidence)
        self.assertEqual(response.json()["claim_verification_status"], "unverified")
        self.assertFalse(response.json()["independently_verified"])
        self.assertEqual(response.json()["source_timestamp"], "2026-10-20T10:00:00Z")
        self.assertEqual(response.json()["source_timestamp_field"], "pushed_at")
        self.assertEqual(
            response.json()["timestamp_semantics"],
            "repository_metadata_timestamp_not_publication",
        )
        self.assertEqual(response.json()["published_at"], response.json()["source_timestamp"])

    def test_unsupported_symbol_returns_http_400_without_source_call(self):
        with patch.object(api, "fetch_github_repository_evidence") as fetch:
            response = client.post("/public-evidence-ingestion", json={"symbol": "BTC"})

        self.assertEqual(response.status_code, 400)
        fetch.assert_not_called()

    def test_non_allowlisted_repository_returns_http_400_without_source_call(self):
        with patch.object(api, "fetch_github_repository_evidence") as fetch:
            response = client.post(
                "/public-evidence-ingestion",
                json={"repository": "attacker/repository"},
            )

        self.assertEqual(response.status_code, 400)
        fetch.assert_not_called()

    def test_source_error_returns_http_502(self):
        with patch.object(
            api,
            "fetch_github_repository_evidence",
            side_effect=EvidenceSourceError("Public GitHub metadata retrieval failed: TimeoutError"),
        ):
            response = client.post("/public-evidence-ingestion", json={})

        self.assertEqual(response.status_code, 502)
        self.assertIn("Public GitHub metadata retrieval failed", response.json()["detail"])

    def test_unexpected_value_error_returns_sanitized_http_502(self):
        with patch.object(
            api,
            "fetch_github_repository_evidence",
            side_effect=ValueError("internal validation details"),
        ):
            response = client.post("/public-evidence-ingestion", json={})

        self.assertEqual(response.status_code, 502)
        self.assertEqual(
            response.json()["detail"],
            "Public evidence provider returned an unexpected response",
        )
        self.assertNotIn("internal validation details", response.text)

    def test_invalid_request_shape_returns_http_422(self):
        response = client.post("/public-evidence-ingestion", json={"symbol": ""})
        self.assertEqual(response.status_code, 422)


    def test_unexpected_provider_error_returns_sanitized_http_502(self):
        with patch.object(
            api,
            "fetch_github_repository_evidence",
            side_effect=RuntimeError("sensitive provider internals"),
        ):
            response = client.post("/public-evidence-ingestion", json={})

        self.assertEqual(response.status_code, 502)
        self.assertEqual(
            response.json()["detail"],
            "Public evidence provider returned an unexpected response",
        )
        self.assertNotIn("sensitive provider internals", response.text)

if __name__ == "__main__":
    unittest.main()
