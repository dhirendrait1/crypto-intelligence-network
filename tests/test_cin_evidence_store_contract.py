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


    def test_provider_namespace_case_is_preserved(self):
        from datetime import datetime, timezone
        from cin_verifiable_evidence import create_claim, create_claim_evidence_relationship

        connection = sqlite3.connect(":memory:")
        try:
            connection.executescript(SCHEMA.read_text(encoding="utf-8"))
            repository = LocalSQLiteEvidenceRepository(connection)
            now = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)

            def bundle(namespace, suffix):
                claim = create_claim(
                    subject="ETH", predicate=f"namespace_case_{suffix}",
                    statement="Namespace case must remain provider-defined.", created_at=now,
                )
                relationship = create_claim_evidence_relationship(
                    claim_id=claim["claim_id"], evidence_id=f"namespace-case-{suffix}",
                    relationship="context_only", rationale="Traceability only.",
                    created_at=now,
                )
                return repository.store_bundle(
                    source_namespace=namespace, external_evidence_id="same-object",
                    evidence_type="provider_record", metadata={"variant": suffix},
                    observed_at="2026-10-30T12:00:00Z", claim=claim,
                    relationship=relationship,
                )

            upper = bundle("Provider", "upper")
            lower = bundle("provider", "lower")
            self.assertNotEqual(upper["cin_evidence_id"], lower["cin_evidence_id"])
            self.assertEqual(
                repository.find_evidence_id(
                    source_namespace="Provider", external_evidence_id="same-object"
                ),
                upper["cin_evidence_id"],
            )
            self.assertEqual(
                repository.find_evidence_id(
                    source_namespace="provider", external_evidence_id="same-object"
                ),
                lower["cin_evidence_id"],
            )
        finally:
            connection.close()

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

    def test_identity_lookup_trims_outer_whitespace_consistently(self):
        from datetime import datetime, timezone
        from cin_verifiable_evidence import create_claim, create_claim_evidence_relationship

        connection = sqlite3.connect(":memory:")
        try:
            connection.executescript(SCHEMA.read_text(encoding="utf-8"))
            repository = LocalSQLiteEvidenceRepository(connection)
            now = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)
            claim = create_claim(
                subject="ETH", predicate="identity_test",
                statement="Provider identity normalization test.", created_at=now,
            )
            relationship = create_claim_evidence_relationship(
                claim_id=claim["claim_id"], evidence_id="identity-test",
                relationship="context_only", rationale="Traceability only.",
                created_at=now,
            )
            bundle = repository.store_bundle(
                source_namespace=" github_public_repository_api ",
                external_evidence_id=" ethereum/go-ethereum ",
                evidence_type="repository_metadata", metadata={"stars": 1},
                observed_at="2026-10-30T12:00:00Z", claim=claim,
                relationship=relationship,
            )
            self.assertEqual(
                repository.find_evidence_id(
                    source_namespace="github_public_repository_api",
                    external_evidence_id="ethereum/go-ethereum",
                ),
                bundle["cin_evidence_id"],
            )
            with self.assertRaises(sqlite3.IntegrityError):
                repository.store_bundle(
                    source_namespace="github_public_repository_api",
                    external_evidence_id="ethereum/go-ethereum",
                    evidence_type="repository_metadata", metadata={"stars": 2},
                    observed_at="2026-10-30T12:01:00Z", claim=claim,
                    relationship=relationship,
                )
        finally:
            connection.close()

    def test_provider_external_id_case_is_preserved_not_folded(self):
        from datetime import datetime, timezone
        from cin_verifiable_evidence import create_claim, create_claim_evidence_relationship

        connection = sqlite3.connect(":memory:")
        try:
            connection.executescript(SCHEMA.read_text(encoding="utf-8"))
            repository = LocalSQLiteEvidenceRepository(connection)
            now = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)
            claim = create_claim(
                subject="ETH", predicate="identity_case_test",
                statement="Case sensitivity must remain provider-defined.", created_at=now,
            )
            relationship = create_claim_evidence_relationship(
                claim_id=claim["claim_id"], evidence_id="identity-case-test",
                relationship="context_only", rationale="Traceability only.",
                created_at=now,
            )
            lower = repository.store_bundle(
                source_namespace="provider", external_evidence_id="Asset-A",
                evidence_type="provider_record", metadata={"v": 1},
                observed_at="2026-10-30T12:00:00Z", claim=claim,
                relationship=relationship,
            )
            second_claim = create_claim(
                subject="ETH", predicate="identity_case_test_second",
                statement="Second provider identity test record.", created_at=now,
            )
            second_relationship = create_claim_evidence_relationship(
                claim_id=second_claim["claim_id"], evidence_id="identity-case-test-second",
                relationship="context_only", rationale="Traceability only.",
                created_at=now,
            )
            upper = repository.store_bundle(
                source_namespace="provider", external_evidence_id="asset-a",
                evidence_type="provider_record", metadata={"v": 2},
                observed_at="2026-10-30T12:01:00Z", claim=second_claim,
                relationship=second_relationship,
            )
            self.assertNotEqual(lower["cin_evidence_id"], upper["cin_evidence_id"])
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM cin_evidence_records WHERE source_namespace='provider'"
                ).fetchone()[0],
                2,
            )
        finally:
            connection.close()

    def test_composite_identity_scopes_external_id_to_source_namespace(self):
        from datetime import datetime, timezone
        from cin_verifiable_evidence import create_claim, create_claim_evidence_relationship

        connection = sqlite3.connect(":memory:")
        try:
            connection.executescript(SCHEMA.read_text(encoding="utf-8"))
            repository = LocalSQLiteEvidenceRepository(connection)
            now = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)

            def store(namespace, suffix):
                claim = create_claim(
                    subject="ETH", predicate=f"namespace_test_{suffix}",
                    statement=f"Evidence identity scoped to {namespace}.", created_at=now,
                )
                relationship = create_claim_evidence_relationship(
                    claim_id=claim["claim_id"], evidence_id=f"namespace-{suffix}",
                    relationship="context_only", rationale="Traceability only.",
                    created_at=now,
                )
                return repository.store_bundle(
                    source_namespace=namespace, external_evidence_id="shared-provider-id",
                    evidence_type="provider_record", metadata={"namespace": namespace},
                    observed_at="2026-10-30T12:00:00Z", claim=claim,
                    relationship=relationship,
                )

            first = store("provider-a", "a")
            second = store("provider-b", "b")
            self.assertNotEqual(first["cin_evidence_id"], second["cin_evidence_id"])
            self.assertEqual(
                repository.find_evidence_id(
                    source_namespace="provider-a",
                    external_evidence_id="shared-provider-id",
                ),
                first["cin_evidence_id"],
            )
            self.assertEqual(
                repository.find_evidence_id(
                    source_namespace="provider-b",
                    external_evidence_id="shared-provider-id",
                ),
                second["cin_evidence_id"],
            )
        finally:
            connection.close()

    def test_null_external_ids_are_not_provider_identity_deduplication_keys(self):
        from datetime import datetime, timezone
        from cin_verifiable_evidence import create_claim, create_claim_evidence_relationship

        connection = sqlite3.connect(":memory:")
        try:
            connection.executescript(SCHEMA.read_text(encoding="utf-8"))
            repository = LocalSQLiteEvidenceRepository(connection)
            now = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)
            results = []
            for suffix in ("first", "second"):
                claim = create_claim(
                    subject="ETH", predicate=f"null_identity_{suffix}",
                    statement=f"Unkeyed evidence record {suffix}.", created_at=now,
                )
                relationship = create_claim_evidence_relationship(
                    claim_id=claim["claim_id"], evidence_id=f"null-{suffix}",
                    relationship="context_only", rationale="Traceability only.",
                    created_at=now,
                )
                results.append(repository.store_bundle(
                    source_namespace="provider-without-stable-id",
                    external_evidence_id=None, evidence_type="unkeyed_record",
                    metadata={"record": suffix}, observed_at="2026-10-30T12:00:00Z",
                    claim=claim, relationship=relationship,
                ))
            self.assertNotEqual(results[0]["cin_evidence_id"], results[1]["cin_evidence_id"])
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM cin_evidence_records "
                    "WHERE source_namespace=? AND external_evidence_id IS NULL",
                    ("provider-without-stable-id",),
                ).fetchone()[0],
                2,
            )
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
