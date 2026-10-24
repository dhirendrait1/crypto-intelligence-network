"""HTTP-level regression tests for the public evidence API."""
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

import cin_evidence_ingestion_api as api
from cin_evidence_ingestion import EvidenceSourceError


app = FastAPI()
app.include_router(api.router)
client = TestClient(app)


class PublicEvidenceHttpTests(unittest.TestCase):
    def test_success_returns_http_200_and_unverified_evidence(self):
        evidence = {
            "symbol": "ETH",
            "retrieval_status": "success",
            "claim_verification_status": "unverified",
            "independently_verified": False,
        }
        with patch.object(api, "fetch_github_repository_evidence", return_value=evidence):
            response = client.post("/public-evidence-ingestion", json={})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), evidence)
        self.assertEqual(response.json()["claim_verification_status"], "unverified")
        self.assertFalse(response.json()["independently_verified"])

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

    def test_invalid_request_shape_returns_http_422(self):
        response = client.post("/public-evidence-ingestion", json={"symbol": ""})
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
