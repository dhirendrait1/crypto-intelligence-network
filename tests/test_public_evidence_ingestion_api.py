"""API-level safety tests for the public evidence ingestion endpoint.

These tests are offline: the GitHub provider is mocked, so CI never depends on
network availability or changes external systems.
"""
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from cin_evidence_ingestion import EvidenceSourceError
from cin_evidence_ingestion_api import PublicEvidenceRequest, public_evidence_ingestion


class PublicEvidenceIngestionApiTests(unittest.TestCase):
    @patch("cin_evidence_ingestion_api.fetch_github_repository_evidence")
    def test_success_preserves_unverified_claim_status(self, fetch):
        expected = {
            "symbol": "ETH",
            "repository": "ethereum/go-ethereum",
            "retrieval_status": "success",
            "claim_verification_status": "unverified",
            "independently_verified": False,
        }
        fetch.return_value = expected

        result = public_evidence_ingestion(
            PublicEvidenceRequest(symbol="ETH", repository="ethereum/go-ethereum")
        )

        self.assertEqual(result, expected)
        fetch.assert_called_once_with("ethereum/go-ethereum")

    def test_rejects_unsupported_symbol_before_provider_call(self):
        with patch("cin_evidence_ingestion_api.fetch_github_repository_evidence") as fetch:
            with self.assertRaises(HTTPException) as raised:
                public_evidence_ingestion(
                    PublicEvidenceRequest(symbol="BTC", repository="ethereum/go-ethereum")
                )

        self.assertEqual(raised.exception.status_code, 400)
        self.assertEqual(raised.exception.detail, "Milestone 2 currently supports ETH only")
        fetch.assert_not_called()

    def test_rejects_repository_outside_allowlist_before_provider_call(self):
        with patch("cin_evidence_ingestion_api.fetch_github_repository_evidence") as fetch:
            with self.assertRaises(HTTPException) as raised:
                public_evidence_ingestion(
                    PublicEvidenceRequest(symbol="ETH", repository="some-user/some-repo")
                )

        self.assertEqual(raised.exception.status_code, 400)
        self.assertEqual(
            raised.exception.detail, "Repository is not on the public-source allowlist"
        )
        fetch.assert_not_called()

    @patch(
        "cin_evidence_ingestion_api.fetch_github_repository_evidence",
        side_effect=EvidenceSourceError("Public source temporarily unavailable"),
    )
    def test_provider_failure_becomes_bad_gateway(self, fetch):
        with self.assertRaises(HTTPException) as raised:
            public_evidence_ingestion(
                PublicEvidenceRequest(symbol="ETH", repository="ethereum/go-ethereum")
            )

        self.assertEqual(raised.exception.status_code, 502)
        self.assertIn("temporarily unavailable", raised.exception.detail)
        fetch.assert_called_once_with("ethereum/go-ethereum")


    @patch(
        "cin_evidence_ingestion_api.fetch_github_repository_evidence",
        side_effect=AttributeError("provider payload had an unexpected shape"),
    )
    def test_unexpected_provider_shape_becomes_generic_bad_gateway(self, fetch):
        with self.assertRaises(HTTPException) as raised:
            public_evidence_ingestion(
                PublicEvidenceRequest(symbol="ETH", repository="ethereum/go-ethereum")
            )
        self.assertEqual(raised.exception.status_code, 502)
        self.assertEqual(
            raised.exception.detail,
            "Public evidence provider returned an unexpected response",
        )
        fetch.assert_called_once_with("ethereum/go-ethereum")


    @patch(
        "cin_evidence_ingestion_api.fetch_github_repository_evidence",
        side_effect=RuntimeError("sensitive provider internals"),
    )
    def test_unexpected_provider_runtime_error_is_sanitized(self, fetch):
        with self.assertRaises(HTTPException) as raised:
            public_evidence_ingestion(
                PublicEvidenceRequest(symbol="ETH", repository="ethereum/go-ethereum")
            )
        self.assertEqual(raised.exception.status_code, 502)
        self.assertEqual(
            raised.exception.detail,
            "Public evidence provider returned an unexpected response",
        )
        self.assertNotIn("sensitive provider internals", raised.exception.detail)
        fetch.assert_called_once_with("ethereum/go-ethereum")

    def test_request_rejects_malformed_symbol_format(self):
        from pydantic import ValidationError

        for symbol in (" ETH", "ETH ", "ETH/USDT", "ETH\n"):
            with self.assertRaises(ValidationError):
                PublicEvidenceRequest(symbol=symbol)

    def test_request_rejects_malformed_repository_path(self):
        from pydantic import ValidationError

        for repository in ("ethereum//go-ethereum", "/go-ethereum", "ethereum/go-ethereum/extra", "ethereum/go ethereum"):
            with self.assertRaises(ValidationError):
                PublicEvidenceRequest(repository=repository)


if __name__ == "__main__":
    unittest.main()

    def test_request_rejects_unknown_fields(self):
        from pydantic import ValidationError

        with self.assertRaises(ValidationError):
            PublicEvidenceRequest(
                symbol="ETH",
                repository="ethereum/go-ethereum",
                repo="ethereum/go-ethereum",
            )

