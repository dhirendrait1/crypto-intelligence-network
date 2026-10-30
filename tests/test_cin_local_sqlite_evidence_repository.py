"""Tests for the explicit local-only SQLite evidence repository."""
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import unittest

from cin_local_sqlite_evidence_repository import LocalSQLiteEvidenceRepository
from cin_verifiable_evidence import create_claim, create_claim_evidence_relationship


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "database" / "migrations" / "0001_claim_evidence_schema_v1.sql"


class TestLocalSQLiteEvidenceRepository(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.executescript(SCHEMA.read_text(encoding="utf-8"))
        self.repo = LocalSQLiteEvidenceRepository(self.db)
        now = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)
        self.claim = create_claim(
            subject="ETH", predicate="developer_activity",
            statement="Repository activity metadata was submitted by caller",
            created_at=now,
        )
        self.relationship = create_claim_evidence_relationship(
            claim_id=self.claim["claim_id"], evidence_id="external-1",
            relationship="context_only",
            rationale="Caller-supplied metadata linked for traceability only.",
            created_at=now,
        )

    def tearDown(self):
        self.db.close()

    def _store(self, external_id="external-1"):
        return self.repo.store_bundle(
            source_namespace="test-provider", external_evidence_id=external_id,
            evidence_type="caller_metadata", metadata={"metric": "commits", "count": 12},
            observed_at="2026-10-30T12:00:00+00:00",
            claim=self.claim, relationship=self.relationship,
        )

    def test_bundle_persists_atomically_and_uses_cin_owned_evidence_id(self):
        result = self._store()
        self.assertEqual(result["persisted"], "true")
        self.assertTrue(result["cin_evidence_id"].startswith("cin-evidence-"))
        evidence = self.db.execute(
            "SELECT source_namespace, external_evidence_id FROM cin_evidence_records WHERE cin_evidence_id=?",
            (result["cin_evidence_id"],),
        ).fetchone()
        self.assertEqual(tuple(evidence), ("test-provider", "external-1"))
        observation = self.db.execute(
            "SELECT retrieved_at, source_status FROM cin_evidence_observations WHERE observation_id=?",
            (result["observation_id"],),
        ).fetchone()
        self.assertEqual(tuple(observation), (None, "caller_supplied"))
        relation = self.db.execute(
            "SELECT cin_evidence_id, relationship_type, review_status FROM cin_claim_evidence_relationships WHERE relationship_id=?",
            (result["relationship_id"],),
        ).fetchone()
        self.assertEqual(tuple(relation), (result["cin_evidence_id"], "context_only", "automated_candidate"))

    def test_duplicate_external_identity_rolls_back_entire_second_bundle(self):
        self._store()
        with self.assertRaises(sqlite3.IntegrityError):
            self._store()
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM cin_evidence_records").fetchone()[0], 1)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM cin_claims").fetchone()[0], 1)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM cin_claim_evidence_relationships").fetchone()[0], 1)

    def test_invalid_naive_timestamp_is_rejected_before_write(self):
        with self.assertRaises(ValueError):
            self.repo.store_bundle(
                source_namespace="test", evidence_type="metadata", metadata={},
                observed_at="2026-10-30T12:00:00", claim=self.claim,
                relationship=self.relationship,
            )
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM cin_evidence_records").fetchone()[0], 0)

    def test_non_finite_metadata_is_rejected(self):
        with self.assertRaises(ValueError):
            self.repo.store_bundle(
                source_namespace="test", evidence_type="metadata", metadata={"value": float("nan")},
                observed_at="2026-10-30T12:00:00Z", claim=self.claim,
                relationship=self.relationship,
            )
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM cin_evidence_records").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
