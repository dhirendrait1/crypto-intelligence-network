"""Reliability regression tests for the local-only CIN SQLite evidence schema."""
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import tempfile
import threading
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



    def test_foreign_keys_reject_observations_without_parent_evidence(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.repo.append_observation(
                cin_evidence_id="missing-parent-evidence",
                metadata={"metric": "commits", "count": 4},
                observed_at="2026-10-30T12:00:00Z",
                source_status="caller_supplied",
            )

        self.assertEqual(
            self.db.execute("SELECT COUNT(*) FROM cin_evidence_observations").fetchone()[0],
            0,
        )

    def test_observations_are_appended_as_distinct_history_rows(self):
        stored = self._store()
        first_id = self.repo.append_observation(
            cin_evidence_id=stored["cin_evidence_id"],
            metadata={"metric": "commits", "count": 5},
            observed_at="2026-10-30T12:01:00Z",
            source_status="caller_supplied",
        )
        second_id = self.repo.append_observation(
            cin_evidence_id=stored["cin_evidence_id"],
            metadata={"metric": "commits", "count": 6},
            observed_at="2026-10-30T12:02:00Z",
            source_status="caller_supplied",
        )

        rows = self.db.execute(
            "SELECT observation_id, metadata_json FROM cin_evidence_observations "
            "WHERE cin_evidence_id=? ORDER BY observed_at",
            (stored["cin_evidence_id"],),
        ).fetchall()
        self.assertEqual(
            [row["observation_id"] for row in rows],
            [stored["observation_id"], first_id, second_id],
        )
        self.assertEqual(
            [row["metadata_json"] for row in rows],
            ['{"count":4,"metric":"commits"}',
             '{"count":5,"metric":"commits"}',
             '{"count":6,"metric":"commits"}'],
        )


    def test_concurrent_duplicate_ingestion_keeps_exactly_one_record(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "cin-concurrency.sqlite3"
            initializer = sqlite3.connect(database_path, timeout=10)
            initializer.executescript(SCHEMA.read_text(encoding="utf-8"))
            initializer.close()

            start = threading.Barrier(2)
            outcomes = []
            outcomes_lock = threading.Lock()

            def ingest(worker_number):
                connection = sqlite3.connect(database_path, timeout=10)
                try:
                    repository = LocalSQLiteEvidenceRepository(connection)
                    claim = create_claim(
                        subject=f"ETH-worker-{worker_number}",
                        predicate="developer_activity",
                        statement=f"Independent caller metadata from worker {worker_number}",
                        created_at=NOW,
                    )
                    relationship = create_claim_evidence_relationship(
                        claim_id=claim["claim_id"],
                        evidence_id=f"external-worker-{worker_number}",
                        relationship="context_only",
                        rationale="Concurrency regression test; not a truth assertion.",
                        created_at=NOW,
                    )
                    start.wait(timeout=5)
                    repository.store_bundle(
                        source_namespace="concurrency-test",
                        external_evidence_id="same-external-id",
                        evidence_type="caller_metadata",
                        metadata={"worker": worker_number},
                        observed_at="2026-10-30T12:00:00Z",
                        claim=claim,
                        relationship=relationship,
                    )
                    outcome = "stored"
                except sqlite3.IntegrityError:
                    outcome = "duplicate_rejected"
                except Exception as exc:
                    outcome = f"unexpected:{type(exc).__name__}:{exc}"
                finally:
                    connection.close()
                with outcomes_lock:
                    outcomes.append(outcome)

            workers = [
                threading.Thread(target=ingest, args=(worker_number,))
                for worker_number in (1, 2)
            ]
            for worker in workers:
                worker.start()
            for worker in workers:
                worker.join(timeout=15)

            self.assertTrue(all(not worker.is_alive() for worker in workers),
                            "concurrent ingestion worker did not finish")
            self.assertCountEqual(outcomes, ["stored", "duplicate_rejected"])

            verification = sqlite3.connect(database_path)
            try:
                self.assertEqual(
                    verification.execute(
                        "SELECT COUNT(*) FROM cin_evidence_records "
                        "WHERE source_namespace=? AND external_evidence_id=?",
                        ("concurrency-test", "same-external-id"),
                    ).fetchone()[0],
                    1,
                )
                self.assertEqual(
                    verification.execute("SELECT COUNT(*) FROM cin_evidence_observations").fetchone()[0],
                    1,
                )
                self.assertEqual(
                    verification.execute("SELECT COUNT(*) FROM cin_claims").fetchone()[0],
                    1,
                )
                self.assertEqual(
                    verification.execute("SELECT COUNT(*) FROM cin_claim_evidence_relationships").fetchone()[0],
                    1,
                )
            finally:
                verification.close()

    def test_assessment_events_are_appended_without_overwriting_prior_history(self):
        stored = self._store()
        first_event_id = self.repo.append_assessment_event(
            claim_id=stored["claim_id"],
            claim_status="supported",
            assessed_at="2026-10-30T12:01:00Z",
            methodology_version="reliability-test-v1",
            assessor_type="automated_rule",
            rationale="First isolated assessment event for history integrity testing.",
        )
        second_event_id = self.repo.append_assessment_event(
            claim_id=stored["claim_id"],
            claim_status="mixed",
            assessed_at="2026-10-30T12:02:00Z",
            methodology_version="reliability-test-v2",
            assessor_type="human_reviewer",
            rationale="Second event must coexist with the earlier assessment.",
        )

        rows = self.db.execute(
            "SELECT assessment_event_id, claim_status, methodology_version "
            "FROM cin_claim_assessment_events WHERE claim_id=? ORDER BY assessed_at",
            (stored["claim_id"],),
        ).fetchall()
        self.assertEqual(
            [row["assessment_event_id"] for row in rows],
            [rows[0]["assessment_event_id"], first_event_id, second_event_id],
        )
        self.assertEqual(
            [row["claim_status"] for row in rows],
            ["not_assessed", "supported", "mixed"],
        )
        self.assertEqual(
            [row["methodology_version"] for row in rows],
            ["initial-unassessed-v1", "reliability-test-v1", "reliability-test-v2"],
        )

    def test_assessment_event_rejects_unknown_claim_without_creating_history(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.repo.append_assessment_event(
                claim_id="cin-claim-does-not-exist",
                claim_status="supported",
                assessed_at="2026-10-30T12:03:00Z",
                methodology_version="reliability-test-v1",
                assessor_type="automated_rule",
                rationale="Foreign-key guard regression test.",
            )

        self.assertEqual(
            self.db.execute("SELECT COUNT(*) FROM cin_claim_assessment_events").fetchone()[0],
            0,
        )

if __name__ == "__main__":
    unittest.main()
