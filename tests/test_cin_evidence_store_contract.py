"""Contract tests for CIN evidence storage adapters."""
import sqlite3
import unittest
from pathlib import Path

from cin_evidence_store import EvidenceStore
from cin_local_sqlite_evidence_repository import LocalSQLiteEvidenceRepository


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "database" / "migrations" / "0001_claim_evidence_schema_v1.sql"


class TestEvidenceStoreContract(unittest.TestCase):
    def test_local_sqlite_repository_structurally_implements_evidence_store(self):
        connection = sqlite3.connect(":memory:")
        try:
            connection.executescript(SCHEMA.read_text(encoding="utf-8"))
            repository = LocalSQLiteEvidenceRepository(connection)
            self.assertIsInstance(repository, EvidenceStore)
        finally:
            connection.close()

    def test_protocol_declares_only_append_oriented_persistence_operations(self):
        operations = {
            name for name in dir(EvidenceStore)
            if not name.startswith("_")
        }
        self.assertEqual(
            operations,
            {"find_evidence_id", "store_bundle", "append_observation", "append_assessment_event"},
        )
        self.assertFalse(hasattr(EvidenceStore, "update_observation"))
        self.assertFalse(hasattr(EvidenceStore, "delete_assessment_event"))


    def test_identity_lookup_returns_none_for_missing_provider_identity(self):
        connection = sqlite3.connect(":memory:")
        try:
            connection.executescript(SCHEMA.read_text(encoding="utf-8"))
            repository = LocalSQLiteEvidenceRepository(connection)
            self.assertIsNone(repository.find_evidence_id(
                source_namespace="github_public_repository_api",
                external_evidence_id="ethereum/go-ethereum",
            ))
        finally:
            connection.close()

    def test_identity_lookup_returns_existing_id_without_mutating_records(self):
        from datetime import datetime, timezone
        from cin_verifiable_evidence import create_claim, create_claim_evidence_relationship

        connection = sqlite3.connect(":memory:")
        try:
            connection.executescript(SCHEMA.read_text(encoding="utf-8"))
            repository = LocalSQLiteEvidenceRepository(connection)
            now = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)
            claim = create_claim(
                subject="ETH",
                predicate="repository_metadata_retrieved",
                statement="Public repository metadata snapshot retrieved.",
                created_at=now,
            )
            relationship = create_claim_evidence_relationship(
                claim_id=claim["claim_id"],
                evidence_id="external-github-go-ethereum",
                relationship="context_only",
                rationale="Source traceability only.",
                created_at=now,
            )
            bundle = repository.store_bundle(
                source_namespace="github_public_repository_api",
                external_evidence_id="ethereum/go-ethereum",
                evidence_type="public_repository_metadata_snapshot",
                metadata={"repository": "ethereum/go-ethereum"},
                observed_at="2026-10-30T12:00:00Z",
                claim=claim,
                relationship=relationship,
                source_status="cin_retrieved",
            )
            before = (
                connection.execute("SELECT COUNT(*) FROM cin_evidence_records").fetchone()[0],
                connection.execute("SELECT COUNT(*) FROM cin_evidence_observations").fetchone()[0],
            )
            found = repository.find_evidence_id(
                source_namespace="github_public_repository_api",
                external_evidence_id="ethereum/go-ethereum",
            )
            after = (
                connection.execute("SELECT COUNT(*) FROM cin_evidence_records").fetchone()[0],
                connection.execute("SELECT COUNT(*) FROM cin_evidence_observations").fetchone()[0],
            )
            self.assertEqual(found, bundle["cin_evidence_id"])
            self.assertEqual(before, after)
        finally:
            connection.close()

if __name__ == "__main__":
    unittest.main()
