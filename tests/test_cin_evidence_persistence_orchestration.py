"""Tests for explicit first-ingestion and repeat-observation orchestration."""
import sqlite3
import unittest

from cin_evidence_persistence import persist_evidence_snapshot


class FakeStore:
    def __init__(self):
        self.identity = None
        self.bundle_calls = []
        self.observation_calls = []
        self.raise_identity_conflict = False

    def find_evidence_id(self, *, source_namespace, external_evidence_id):
        if self.identity == (source_namespace, external_evidence_id):
            return "cin-evidence-existing"
        return None

    def store_bundle(self, **kwargs):
        self.bundle_calls.append(kwargs)
        if self.raise_identity_conflict:
            self.raise_identity_conflict = False
            self.identity = (kwargs["source_namespace"], kwargs["external_evidence_id"])
            connection = sqlite3.connect(":memory:")
            try:
                connection.execute(
                    "CREATE TABLE cin_evidence_records "
                    "(source_namespace TEXT, external_evidence_id TEXT)"
                )
                connection.execute(
                    "CREATE UNIQUE INDEX uq_cin_evidence_external_identity "
                    "ON cin_evidence_records(source_namespace, external_evidence_id)"
                )
                connection.execute(
                    "INSERT INTO cin_evidence_records VALUES ('github_public_repository_api', 'ethereum/go-ethereum')"
                )
                connection.execute(
                    "INSERT INTO cin_evidence_records VALUES ('github_public_repository_api', 'ethereum/go-ethereum')"
                )
            except sqlite3.IntegrityError as exc:
                raise exc
            finally:
                connection.close()
        self.identity = (kwargs["source_namespace"], kwargs["external_evidence_id"])
        return {
            "cin_evidence_id": "cin-evidence-created",
            "observation_id": "cin-observation-first",
            "persisted": "true",
            "storage_mode": "test",
        }

    def append_observation(self, **kwargs):
        self.observation_calls.append(kwargs)
        return f"observation-{len(self.observation_calls)}"


class TestEvidencePersistenceOrchestration(unittest.TestCase):
    def setUp(self):
        self.store = FakeStore()
        self.common = dict(
            source_namespace="github_public_repository_api",
            external_evidence_id="ethereum/go-ethereum",
            evidence_type="public_repository_metadata_snapshot",
            metadata={"stars": 100},
            observed_at="2026-10-30T12:00:00Z",
            claim={"claim_id": "claim-1"},
            relationship={"claim_id": "claim-1"},
            source_status="cin_retrieved",
            retrieved_at="2026-10-30T12:00:00Z",
        )

    def test_first_ingestion_creates_one_bundle(self):
        result = persist_evidence_snapshot(self.store, **self.common)
        self.assertEqual(result["operation"], "bundle_created")
        self.assertEqual(result["cin_evidence_id"], "cin-evidence-created")
        self.assertEqual(len(self.store.bundle_calls), 1)
        self.assertEqual(self.store.observation_calls, [])

    def test_repeat_ingestion_appends_observation_without_creating_bundle(self):
        self.store.identity = (
            self.common["source_namespace"], self.common["external_evidence_id"]
        )
        result = persist_evidence_snapshot(self.store, **self.common)
        self.assertEqual(result["operation"], "observation_appended")
        self.assertEqual(result["cin_evidence_id"], "cin-evidence-existing")
        self.assertEqual(self.store.bundle_calls, [])
        self.assertEqual(len(self.store.observation_calls), 1)

    def test_concurrent_first_ingestion_conflict_appends_to_winning_record(self):
        self.store.raise_identity_conflict = True
        result = persist_evidence_snapshot(self.store, **self.common)
        self.assertEqual(
            result["operation"], "observation_appended_after_identity_race"
        )
        self.assertEqual(result["cin_evidence_id"], "cin-evidence-existing")
        self.assertEqual(len(self.store.bundle_calls), 1)
        self.assertEqual(len(self.store.observation_calls), 1)

    def test_integrity_error_without_winning_identity_is_propagated(self):
        class BrokenStore(FakeStore):
            def store_bundle(self, **kwargs):
                raise sqlite3.IntegrityError("unrelated constraint failure")

        with self.assertRaisesRegex(sqlite3.IntegrityError, "unrelated constraint"):
            persist_evidence_snapshot(BrokenStore(), **self.common)

    def test_unrelated_integrity_error_is_not_recovered_even_if_identity_exists(self):
        class BrokenStore(FakeStore):
            def store_bundle(self, **kwargs):
                self.identity = (kwargs["source_namespace"], kwargs["external_evidence_id"])
                connection = sqlite3.connect(":memory:")
                try:
                    connection.execute("CREATE TABLE parent (id INTEGER PRIMARY KEY)")
                    connection.execute(
                        "CREATE TABLE child (parent_id INTEGER REFERENCES parent(id))"
                    )
                    connection.execute("PRAGMA foreign_keys = ON")
                    connection.execute("INSERT INTO child VALUES (999)")
                except sqlite3.IntegrityError as exc:
                    raise exc
                finally:
                    connection.close()

        broken = BrokenStore()
        with self.assertRaises(sqlite3.IntegrityError) as caught:
            persist_evidence_snapshot(broken, **self.common)
        self.assertEqual(
            caught.exception.sqlite_errorcode,
            sqlite3.SQLITE_CONSTRAINT_FOREIGNKEY,
        )
        self.assertEqual(broken.observation_calls, [])

    def test_non_integrity_persistence_failure_is_not_swallowed(self):
        class BrokenStore(FakeStore):
            def store_bundle(self, **kwargs):
                raise OSError("storage unavailable")

        with self.assertRaisesRegex(OSError, "storage unavailable"):
            persist_evidence_snapshot(BrokenStore(), **self.common)


if __name__ == "__main__":
    unittest.main()
