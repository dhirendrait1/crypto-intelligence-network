"""Route-level contract tests for CIN public evidence ingestion."""
import unittest
from unittest.mock import patch

from fastapi import HTTPException

import cin_evidence_ingestion_api as api
from cin_evidence_ingestion import EvidenceSourceError


class PublicEvidenceIngestionApiTests(unittest.TestCase):
    def test_success_returns_unverified_evidence_contract(self):
        evidence = {
            "symbol": "ETH",
            "retrieval_status": "success",
            "claim_verification_status": "unverified",
            "independently_verified": False,
            "metadata_completeness": "partial",
            "metadata_missing_fields": ["pushed_at"],
        }
        request = api.PublicEvidenceRequest(repository="ethereum/go-ethereum")
        with patch.object(api, "fetch_github_repository_evidence", return_value=evidence) as fetch:
            result = api.public_evidence_ingestion(request)

        self.assertEqual(result, evidence)
        fetch.assert_called_once_with("ethereum/go-ethereum")
        self.assertEqual(result["claim_verification_status"], "unverified")
        self.assertFalse(result["independently_verified"])

    def test_rejects_non_eth_symbol_before_source_call(self):
        request = api.PublicEvidenceRequest(symbol="BTC")
        with patch.object(api, "fetch_github_repository_evidence") as fetch:
            with self.assertRaises(HTTPException) as raised:
                api.public_evidence_ingestion(request)

        self.assertEqual(raised.exception.status_code, 400)
        fetch.assert_not_called()

    def test_rejects_repository_outside_allowlist_before_source_call(self):
        request = api.PublicEvidenceRequest(repository="attacker/repository")
        with patch.object(api, "fetch_github_repository_evidence") as fetch:
            with self.assertRaises(HTTPException) as raised:
                api.public_evidence_ingestion(request)

        self.assertEqual(raised.exception.status_code, 400)
        fetch.assert_not_called()

    def test_source_failure_maps_to_bad_gateway(self):
        request = api.PublicEvidenceRequest()
        with patch.object(
            api, "fetch_github_repository_evidence",
            side_effect=EvidenceSourceError("Public GitHub metadata retrieval failed: TimeoutError"),
        ):
            with self.assertRaises(HTTPException) as raised:
                api.public_evidence_ingestion(request)

        self.assertEqual(raised.exception.status_code, 502)
        self.assertIn("Public GitHub metadata retrieval failed", raised.exception.detail)

    def test_connector_value_error_maps_to_bad_request(self):
        request = api.PublicEvidenceRequest()
        with patch.object(
            api, "fetch_github_repository_evidence",
            side_effect=ValueError("timeout must be between 1 and 15 seconds"),
        ):
            with self.assertRaises(HTTPException) as raised:
                api.public_evidence_ingestion(request)

        self.assertEqual(raised.exception.status_code, 400)
        self.assertIn("timeout must be between", raised.exception.detail)


if __name__ == "__main__":
    unittest.main()
