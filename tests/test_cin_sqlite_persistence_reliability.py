"""Reliability regression tests for the local-only CIN SQLite evidence schema."""
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import unittest

from cin_local_sqlite_evidence_repository import LocalSQLiteEvidenceRepository
from cin_verifiable_evidence import create_claim, create_claim_evidence_relationship


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "database" / "migrations" / "0001_claim_evidence_schema_v1.sql"
NOW = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)


class TestSQLitePersistenceReliability(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.executescript(SCHEMA.read_text(encoding="utf-8"))
        self.repo = LocalSQLiteEvidenceRepository(self.db)
        self.claim = create_claim(
            subject="ETH",
            predicate="developer_activity",
            statement="Caller supplied repository activity metadata",
            created_at=NOW,
        )
        self.relationship = create_claim_evidence_relationship(
            claim_id=self.claim["claim_id"],
            evidence_id="external-reliability-test",
            relationship="context_only",
            rationale="Traceability only; this link does not establish claim truth.",
            created_at=NOW,
        )

    def tearDown(self):
        self.db.close()

    def _store(self):
        return self.repo.store_bundle(
            source_namespace="reliability-test",
            external_evidence_id="evidence-rollback-001",
            evidence_type="caller_metadata",
            metadata={"metric": "commits", "count": 4},
            observed_at="2026-10-30T12:00:00Z",
            claim=self.claim,
            relationship=self.relationship,
        )

    def test_failure_after_parent_and_claim_inserts_rolls_back_entire_bundle(self):
        self.db.execute(
            """
            CREATE TRIGGER reject_relationship_insert
            BEFORE INSERT ON cin_claim_evidence_relationships
            BEGIN
                SELECT RAISE(ABORT, 'injected relationship write failure');
            END;
            """
        )

        with self.assertRaisesRegex(sqlite3.IntegrityError, "injected relationship write failure"):
            self._store()

        for table in (
            "cin_evidence_records",
            "cin_evidence_observations",
            "cin_claims",
            "cin_claim_assessment_events",
            "cin_claim_evidence_relationships",
        ):
            with self.subTest(table=table):
                self.assertEqual(
                    self.db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0],
                    0,
                )

    def test_migration_can_be_applied_twice_without_duplicate_schema_objects(self):
        migration = SCHEMA.read_text(encoding="utf-8")
        self.db.executescript(migration)
        self.db.executescript(migration)

        migration_versions = self.db.execute(
            "SELECT version FROM cin_schema_migrations ORDER BY version"
        ).fetchall()
        self.assertEqual([row[0] for row in migration_versions], ["1.0"])

        table_names = {
            row[0]
            for row in self.db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'cin_%'"
            ).fetchall()
        }
        self.assertEqual(
            table_names,
            {
                "cin_schema_migrations",
                "cin_evidence_records",
                "cin_evidence_observations",
                "cin_claims",
                "cin_claim_assessment_events",
                "cin_claim_evidence_relationships",
                "cin_evidence_conflicts",
                "cin_evidence_conflict_observations",
            },
        )

    def test_failed_bundle_does_not_reserve_external_evidence_identity(self):
        self.db.execute(
            """
            CREATE TRIGGER reject_relationship_insert
            BEFORE INSERT ON cin_claim_evidence_relationships
            BEGIN
                SELECT RAISE(ABORT, 'injected relationship write failure');
            END;
            """
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self._store()

        self.db.execute("DROP TRIGGER reject_relationship_insert")
        result = self._store()
        self.assertEqual(result["persisted"], "true")
        self.assertEqual(
            self.db.execute(
                "SELECT COUNT(*) FROM cin_evidence_records "
                "WHERE source_namespace=? AND external_evidence_id=?",
                ("reliability-test", "evidence-rollback-001"),
            ).fetchone()[0],
            1,
        )


if __name__ == "__main__":
    unittest.main()
