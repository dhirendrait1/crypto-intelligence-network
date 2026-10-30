"""Real SQLite integration tests for evidence persistence orchestration."""
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import tempfile
import threading
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

    def test_observation_fingerprints_and_provenance_timestamps_are_preserved(self):
        first = persist_evidence_snapshot(self.repository, **self.arguments)
        repeated = dict(self.arguments)
        repeated["metadata"] = {"stars": 105, "forks": 21}
        repeated["observed_at"] = "2026-10-30T12:05:00Z"
        repeated["retrieved_at"] = "2026-10-30T12:06:00Z"
        repeated["published_at"] = "2026-10-29T18:30:00+05:30"
        repeated["checked_at"] = "2026-10-30T12:07:00Z"
        second = persist_evidence_snapshot(self.repository, **repeated)

        rows = self.connection.execute(
            """
            SELECT observed_at, retrieved_at, published_at, checked_at,
                   metadata_json, metadata_fingerprint_sha256, source_status
            FROM cin_evidence_observations
            WHERE cin_evidence_id = ?
            ORDER BY observed_at
            """,
            (first["cin_evidence_id"],),
        ).fetchall()

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["observed_at"], "2026-10-30T12:00:00Z")
        self.assertEqual(rows[0]["retrieved_at"], "2026-10-30T12:00:00Z")
        self.assertIsNone(rows[0]["published_at"])
        self.assertIsNone(rows[0]["checked_at"])
        self.assertEqual(rows[0]["source_status"], "cin_retrieved")
        self.assertEqual(rows[1]["observed_at"], "2026-10-30T12:05:00Z")
        self.assertEqual(rows[1]["retrieved_at"], "2026-10-30T12:06:00Z")
        self.assertEqual(rows[1]["published_at"], "2026-10-29T13:00:00Z")
        self.assertEqual(rows[1]["checked_at"], "2026-10-30T12:07:00Z")
        self.assertEqual(rows[1]["source_status"], "cin_retrieved")
        self.assertNotEqual(
            rows[0]["metadata_fingerprint_sha256"],
            rows[1]["metadata_fingerprint_sha256"],
        )
        self.assertEqual(second["operation"], "observation_appended")

    def test_repeat_ingestion_survives_reopening_database_connection(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "cin-evidence.sqlite3"
            first_connection = sqlite3.connect(database_path)
            first_connection.executescript(SCHEMA.read_text(encoding="utf-8"))
            first_repository = LocalSQLiteEvidenceRepository(first_connection)
            first = persist_evidence_snapshot(first_repository, **self.arguments)
            first_connection.close()

            reopened_connection = sqlite3.connect(database_path)
            reopened_repository = LocalSQLiteEvidenceRepository(reopened_connection)
            repeated = dict(self.arguments)
            repeated["metadata"] = {"stars": 111, "forks": 22}
            repeated["observed_at"] = "2026-10-30T12:15:00Z"
            repeated["retrieved_at"] = "2026-10-30T12:15:00Z"
            second = persist_evidence_snapshot(reopened_repository, **repeated)

            self.assertEqual(second["operation"], "observation_appended")
            self.assertEqual(first["cin_evidence_id"], second["cin_evidence_id"])
            self.assertEqual(
                reopened_connection.execute(
                    "SELECT COUNT(*) FROM cin_evidence_records"
                ).fetchone()[0],
                1,
            )
            self.assertEqual(
                reopened_connection.execute(
                    "SELECT COUNT(*) FROM cin_evidence_observations"
                ).fetchone()[0],
                2,
            )
            reopened_connection.close()

    def test_stale_parallel_lookup_recovers_from_real_sqlite_identity_conflict(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "cin-race.sqlite3"
            first_connection = sqlite3.connect(database_path)
            first_connection.executescript(SCHEMA.read_text(encoding="utf-8"))
            second_connection = sqlite3.connect(database_path)
            first_repository = LocalSQLiteEvidenceRepository(first_connection)
            second_repository = LocalSQLiteEvidenceRepository(second_connection)

            first = persist_evidence_snapshot(first_repository, **self.arguments)

            class StaleLookupRepository:
                def __init__(self, delegate):
                    self.delegate = delegate
                    self.first_lookup = True

                def find_evidence_id(self, **kwargs):
                    if self.first_lookup:
                        self.first_lookup = False
                        # Model a second worker whose identity read happened
                        # just before the first worker committed its bundle.
                        return None
                    return self.delegate.find_evidence_id(**kwargs)

                def store_bundle(self, **kwargs):
                    return self.delegate.store_bundle(**kwargs)

                def append_observation(self, **kwargs):
                    return self.delegate.append_observation(**kwargs)

                def append_assessment_event(self, **kwargs):
                    return self.delegate.append_assessment_event(**kwargs)

            second_arguments = dict(self.arguments)
            second_arguments["metadata"] = {"stars": 120, "forks": 25}
            second_arguments["observed_at"] = "2026-10-30T12:20:00Z"
            second_arguments["retrieved_at"] = "2026-10-30T12:20:00Z"
            second = persist_evidence_snapshot(
                StaleLookupRepository(second_repository), **second_arguments
            )

            self.assertEqual(
                second["operation"], "observation_appended_after_identity_race"
            )
            self.assertEqual(first["cin_evidence_id"], second["cin_evidence_id"])
            self.assertEqual(
                second_connection.execute(
                    "SELECT COUNT(*) FROM cin_evidence_records"
                ).fetchone()[0],
                1,
            )
            self.assertEqual(
                second_connection.execute(
                    "SELECT COUNT(*) FROM cin_evidence_observations"
                ).fetchone()[0],
                2,
            )
            first_connection.close()
            second_connection.close()

    def test_simultaneous_first_ingestion_from_two_connections(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "cin-simultaneous-race.sqlite3"
            setup = sqlite3.connect(database_path)
            setup.executescript(SCHEMA.read_text(encoding="utf-8"))
            setup.close()

            lookup_barrier = threading.Barrier(2)
            results = []
            errors = []
            result_lock = threading.Lock()

            class SynchronizedLookupRepository:
                def __init__(self, connection):
                    self.delegate = LocalSQLiteEvidenceRepository(connection)
                    self.first_lookup = True

                def find_evidence_id(self, **kwargs):
                    # Synchronize only the initial lookup. A worker resolving a
                    # uniqueness race performs a second lookup after the winner
                    # has committed and must not wait at the barrier again.
                    if self.first_lookup:
                        self.first_lookup = False
                        lookup_barrier.wait(timeout=10)
                    return self.delegate.find_evidence_id(**kwargs)

                def store_bundle(self, **kwargs):
                    return self.delegate.store_bundle(**kwargs)

                def append_observation(self, **kwargs):
                    return self.delegate.append_observation(**kwargs)

                def append_assessment_event(self, **kwargs):
                    return self.delegate.append_assessment_event(**kwargs)

            def ingest(stars, minute):
                connection = sqlite3.connect(database_path, timeout=15)
                try:
                    repository = SynchronizedLookupRepository(connection)
                    arguments = dict(self.arguments)
                    arguments["metadata"] = {"stars": stars, "forks": 30}
                    arguments["observed_at"] = f"2026-10-30T12:{minute:02d}:00Z"
                    arguments["retrieved_at"] = f"2026-10-30T12:{minute:02d}:00Z"
                    value = persist_evidence_snapshot(repository, **arguments)
                    with result_lock:
                        results.append(value)
                except BaseException as exc:
                    with result_lock:
                        errors.append(exc)
                finally:
                    connection.close()

            threads = [
                threading.Thread(target=ingest, args=(130, 21)),
                threading.Thread(target=ingest, args=(131, 22)),
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=20)

            self.assertTrue(all(not thread.is_alive() for thread in threads))
            self.assertEqual(errors, [])
            self.assertEqual(len(results), 2)
            self.assertEqual(
                len({item["cin_evidence_id"] for item in results}), 1
            )
            self.assertEqual(
                sum(item["operation"] == "bundle_created" for item in results), 1
            )
            self.assertEqual(
                sum(
                    item["operation"] in {
                        "observation_appended",
                        "observation_appended_after_identity_race",
                    }
                    for item in results
                ),
                1,
            )
            verification = sqlite3.connect(database_path)
            self.assertEqual(
                verification.execute(
                    "SELECT COUNT(*) FROM cin_evidence_records"
                ).fetchone()[0],
                1,
            )
            self.assertEqual(
                verification.execute(
                    "SELECT COUNT(*) FROM cin_evidence_observations"
                ).fetchone()[0],
                2,
            )
            verification.close()

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
