"""Guard the public evidence API's read-only persistence boundary."""
import ast
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from fastapi import HTTPException

import cin_evidence_ingestion_api as api


ROOT = Path(__file__).resolve().parents[1]
API_SOURCE = ROOT / "cin_evidence_ingestion_api.py"


class TestEvidenceIngestionAPIStorageBoundary(unittest.TestCase):
    def test_api_module_does_not_import_or_initialize_a_storage_backend(self):
        tree = ast.parse(API_SOURCE.read_text(encoding="utf-8"))
        imported_modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.add(node.module)

        self.assertFalse(any("sqlite" in name.lower() for name in imported_modules))
        self.assertIn("cin_evidence_store", imported_modules)
        self.assertNotIn("cin_local_sqlite_evidence_repository", imported_modules)

    def test_successful_provider_response_is_returned_without_persistence_claim(self):
        provider_payload = {
            "symbol": "ETH",
            "repository": "ethereum/go-ethereum",
            "retrieval_status": "success",
            "claim_verification_status": "unverified",
            "independently_verified": False,
        }
        request = api.PublicEvidenceRequest(
            symbol="ETH", repository="ethereum/go-ethereum"
        )
        with patch.object(api, "fetch_github_repository_evidence", return_value=provider_payload) as fetch:
            result = api.public_evidence_ingestion(request, store=None)

        self.assertEqual(result, provider_payload)
        fetch.assert_called_once_with("ethereum/go-ethereum")
        self.assertFalse(result["independently_verified"])
        self.assertEqual(result["claim_verification_status"], "unverified")

    def test_provider_error_is_returned_as_controlled_502(self):
        request = api.PublicEvidenceRequest(
            symbol="ETH", repository="ethereum/go-ethereum"
        )
        with patch.object(
            api, "fetch_github_repository_evidence",
            side_effect=api.EvidenceSourceError("upstream unavailable"),
        ):
            with self.assertRaises(HTTPException) as raised:
                api.public_evidence_ingestion(request)

        self.assertEqual(raised.exception.status_code, 502)
        self.assertEqual(
            raised.exception.detail,
            "Public evidence provider is temporarily unavailable",
        )

    def test_provider_error_never_exposes_injected_sensitive_details(self):
        request = api.PublicEvidenceRequest(
            symbol="ETH", repository="ethereum/go-ethereum"
        )
        secret_markers = (
            "RAW_PROVIDER_BODY_SECRET",
            "ghp_SUPER_SECRET_TOKEN",
            "Bearer top-secret-credential",
            "access_token=private-query-secret",
            "https://api.github.com/private?token=url-secret",
        )
        for marker in secret_markers:
            with self.subTest(marker=marker):
                with patch.object(
                    api,
                    "fetch_github_repository_evidence",
                    side_effect=api.EvidenceSourceError(
                        f"provider failed: {marker}; body=RAW_PROVIDER_BODY_SECRET"
                    ),
                ):
                    with self.assertRaises(HTTPException) as raised:
                        api.public_evidence_ingestion(request)

                self.assertEqual(raised.exception.status_code, 502)
                response_text = str(raised.exception.detail)
                self.assertEqual(
                    response_text,
                    "Public evidence provider is temporarily unavailable",
                )
                for sensitive in secret_markers:
                    self.assertNotIn(sensitive, response_text)

    def test_unexpected_provider_error_does_not_leak_internal_details(self):
        request = api.PublicEvidenceRequest(
            symbol="ETH", repository="ethereum/go-ethereum"
        )
        with patch.object(
            api, "fetch_github_repository_evidence",
            side_effect=RuntimeError("sensitive internal detail"),
        ):
            with self.assertRaises(HTTPException) as raised:
                api.public_evidence_ingestion(request)

        self.assertEqual(raised.exception.status_code, 502)
        self.assertEqual(
            raised.exception.detail,
            "Public evidence provider is temporarily unavailable",
        )
        self.assertNotIn("sensitive internal detail", raised.exception.detail)

    def test_non_eth_symbol_is_rejected_before_provider_call(self):
        request = api.PublicEvidenceRequest(
            symbol="BTC", repository="ethereum/go-ethereum"
        )
        with patch.object(api, "fetch_github_repository_evidence") as fetch:
            with self.assertRaises(HTTPException) as raised:
                api.public_evidence_ingestion(request)

        self.assertEqual(raised.exception.status_code, 400)
        fetch.assert_not_called()

    def test_repository_outside_allowlist_is_rejected_before_provider_call(self):
        request = api.PublicEvidenceRequest(
            symbol="ETH", repository="attacker/unknown-repository"
        )
        with patch.object(api, "fetch_github_repository_evidence") as fetch:
            with self.assertRaises(HTTPException) as raised:
                api.public_evidence_ingestion(request)

        self.assertEqual(raised.exception.status_code, 400)
        fetch.assert_not_called()


    def test_dependency_returns_none_when_application_has_no_store(self):
        from types import SimpleNamespace

        request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))
        self.assertIsNone(api.get_evidence_store(request))

    def test_dependency_returns_only_explicitly_configured_store(self):
        from types import SimpleNamespace

        sentinel_store = object()
        request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(cin_evidence_store=sentinel_store)))
        self.assertIs(api.get_evidence_store(request), sentinel_store)

    def test_injected_store_is_not_written_by_read_only_endpoint(self):
        store = Mock()
        request = api.PublicEvidenceRequest(symbol="ETH", repository="ethereum/go-ethereum")
        payload = {"symbol": "ETH", "claim_verification_status": "unverified"}
        with patch.object(api, "fetch_github_repository_evidence", return_value=payload):
            result = api.public_evidence_ingestion(request, store=store)
        self.assertEqual(result, payload)
        store.store_bundle.assert_not_called()
        store.append_observation.assert_not_called()
        store.append_assessment_event.assert_not_called()

if __name__ == "__main__":
    unittest.main()
