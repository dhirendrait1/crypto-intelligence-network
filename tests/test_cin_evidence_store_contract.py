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
            {"store_bundle", "append_observation", "append_assessment_event"},
        )
        self.assertFalse(hasattr(EvidenceStore, "update_observation"))
        self.assertFalse(hasattr(EvidenceStore, "delete_assessment_event"))


if __name__ == "__main__":
    unittest.main()
