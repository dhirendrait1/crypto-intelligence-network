"""Validate the reference CIN evidence schema using stdlib SQLite in memory."""
from pathlib import Path
import sqlite3
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "database" / "migrations" / "0001_claim_evidence_schema_v1.sql"


class TestCINEvidenceSchemaV1(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.executescript(SCHEMA.read_text(encoding="utf-8"))

    def tearDown(self):
        self.db.close()

    def test_schema_creates_expected_entities_and_indexes(self):
        names = {
            row[0] for row in self.db.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'index')"
            )
        }
        for name in (
            "cin_evidence_records",
            "cin_evidence_observations",
            "cin_claims",
            "cin_claim_assessment_events",
            "cin_claim_evidence_relationships",
            "cin_evidence_conflicts",
            "cin_evidence_conflict_observations",
            "uq_cin_evidence_external_identity",
            "ix_cin_evidence_observations_record_time",
        ):
            self.assertIn(name, names)

    def test_external_evidence_identity_is_namespaced_and_unique(self):
        self.db.execute(
            """INSERT INTO cin_evidence_records
               VALUES ('ev-1', 'provider-a', 'same-id', 'report', '2026-10-30T00:00:00Z', '1.0')"""
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute(
                """INSERT INTO cin_evidence_records
                   VALUES ('ev-2', 'provider-a', 'same-id', 'report', '2026-10-30T00:00:00Z', '1.0')"""
            )
        self.db.execute(
            """INSERT INTO cin_evidence_records
               VALUES ('ev-3', 'provider-b', 'same-id', 'report', '2026-10-30T00:00:00Z', '1.0')"""
        )

    def test_relationship_requires_existing_claim_and_evidence(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute(
                """INSERT INTO cin_claim_evidence_relationships
                   VALUES ('rel-1', 'missing-claim', 'missing-evidence', 'context_only',
                           'automated_candidate', 'trace only', '2026-10-30T00:00:00Z', '1.0')"""
            )

    def test_claim_assessment_vocabulary_is_constrained(self):
        self.db.execute(
            """INSERT INTO cin_claims
               VALUES ('claim-1', 'ETH', 'developer_activity', 'Repo activity observed',
                       NULL, NULL, NULL, NULL, '2026-10-30T00:00:00Z', '1.0',
                       'sha256_canonical_claim_identity_v1')"""
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute(
                """INSERT INTO cin_claim_assessment_events
                   VALUES ('event-1', 'claim-1', 'verified', '2026-10-30T00:00:00Z',
                           'method-1', 'automated_rule', 'unsupported status')"""
            )

    def test_observation_requires_existing_evidence_record_and_valid_json(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute(
                """INSERT INTO cin_evidence_observations
                   VALUES ('obs-1', 'missing-evidence', '2026-10-30T00:00:00Z', NULL, NULL,
                           NULL, '{}', ?, NULL, 'caller_supplied', '1.0')""",
                ("a" * 64,),
            )
        self.db.execute(
            """INSERT INTO cin_evidence_records
               VALUES ('ev-1', 'caller', NULL, 'metadata', '2026-10-30T00:00:00Z', '1.0')"""
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute(
                """INSERT INTO cin_evidence_observations
                   VALUES ('obs-2', 'ev-1', '2026-10-30T00:00:00Z', NULL, NULL,
                           NULL, 'not-json', ?, NULL, 'caller_supplied', '1.0')""",
                ("a" * 64,),
            )


if __name__ == "__main__":
    unittest.main()
