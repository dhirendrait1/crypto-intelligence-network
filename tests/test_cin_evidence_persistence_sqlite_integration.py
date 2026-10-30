"""Real SQLite integration tests for evidence persistence orchestration."""
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import unittest

from cin_evidence_persistence import persist_evidence_snapshot
from cin_local_sqlite_evidence_repository import LocalSQLiteEvidenceRepository
from cin_verifiable_evidence import create_claim, create_claim_evidence_relationship


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "database" / "migrations" / "0001_claim_evidence_schema_v1.sql"
NOW = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)


class TestEvidencePersistenceSQLiteIntegration(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        self.connection.executescript(SCHEMA.read_text(encoding="utf-8"))
        self.repository = LocalSQLiteEvidenceRepository(self.connection)
        self.claim = create_claim(
            subject="ETH",
            predicate="repository_metadata_snapshot_observed",
            statement="A public repository metadata snapshot was observed.",
            created_at=NOW,
        )
        self.relationship = create_claim_evidence_relationship(
            claim_id=self.claim["claim_id"],
            evidence_id="external-github-ethereum-go-ethereum",
            relationship="context_only",
            rationale="Repository metadata is contextual traceability, not investment evidence.",
            created_at=NOW,
        )
        self.arguments = dict(
            source_namespace="github_public_repository_api",
            external_evidence_id="ethereum/go-ethereum",
            evidence_type="public_repository_metadata_snapshot",
            metadata={"stars": 100, "forks": 20},
            observed_at="2026-10-30T12:00:00Z",
            claim=self.claim,
            relationship=self.relationship,
            source_status="cin_retrieved",
            retrieved_at="2026-10-30T12:00:00Z",
        )

    def tearDown(self):
        self.connection.close()

    def test_first_and_repeat_ingestion_use_one_record_and_append_history(self):
        first = persist_evidence_snapshot(self.repository, **self.arguments)
        second_arguments = dict(self.arguments)
        second_arguments["metadata"] = {"stars": 105, "forks": 21}
        second_arguments["observed_at"] = "2026-10-30T12:05:00Z"
        second_arguments["retrieved_at"] = "2026-10-30T12:05:00Z"

        second = persist_evidence_snapshot(self.repository, **second_arguments)

        self.assertEqual(first["operation"], "bundle_created")
        self.assertEqual(second["operation"], "observation_appended")
        self.assertEqual(first["cin_evidence_id"], second["cin_evidence_id"])
        self.assertNotEqual(first["observation_id"], second["observation_id"])
        self.assertEqual(
            self.connection.execute("SELECT COUNT(*) FROM cin_evidence_records").fetchone()[0],
            1,
        )
        self.assertEqual(
            self.connection.execute("SELECT COUNT(*) FROM cin_evidence_observations").fetchone()[0],
            2,
        )
        self.assertEqual(
            self.connection.execute("SELECT COUNT(*) FROM cin_claims").fetchone()[0],
            1,
        )
        self.assertEqual(
            self.connection.execute("SELECT COUNT(*) FROM cin_claim_evidence_relationships").fetchone()[0],
            1,
        )
        observations = self.connection.execute(
            "SELECT metadata_json FROM cin_evidence_observations "
            "WHERE cin_evidence_id=? ORDER BY observed_at",
            (first["cin_evidence_id"],),
        ).fetchall()
        self.assertEqual(
            [row[0] for row in observations],
            ['{"forks":20,"stars":100}', '{"forks":21,"stars":105}'],
        )

    def test_existing_identity_is_not_mutated_when_observation_append_fails(self):
        first = persist_evidence_snapshot(self.repository, **self.arguments)
        self.connection.execute(
            """
            CREATE TRIGGER reject_observation_insert
            BEFORE INSERT ON cin_evidence_observations
            WHEN NEW.observation_id != ?
            BEGIN
                SELECT RAISE(ABORT, 'injected observation failure');
            END;
            """.replace("?", "'never-match'")
        )
        changed = dict(self.arguments)
        changed["metadata"] = {"stars": 999}
        changed["observed_at"] = "2026-10-30T12:10:00Z"
        with self.assertRaisesRegex(sqlite3.IntegrityError, "injected observation failure"):
            persist_evidence_snapshot(self.repository, **changed)
        self.assertEqual(
            self.connection.execute("SELECT COUNT(*) FROM cin_evidence_records").fetchone()[0],
            1,
        )
        self.assertEqual(
            self.connection.execute("SELECT COUNT(*) FROM cin_evidence_observations").fetchone()[0],
            1,
        )
        self.assertEqual(
            self.repository.find_evidence_id(
                source_namespace=self.arguments["source_namespace"],
                external_evidence_id=self.arguments["external_evidence_id"],
            ),
            first["cin_evidence_id"],
        )


if __name__ == "__main__":
    unittest.main()
