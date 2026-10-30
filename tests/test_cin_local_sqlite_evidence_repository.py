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


    def test_assessment_events_are_append_only_and_preserve_history(self):
        result = self._store()
        first = self.db.execute(
            "SELECT claim_status FROM cin_claim_assessment_events WHERE claim_id=?",
            (result["claim_id"],),
        ).fetchone()[0]
        event_id = self.repo.append_assessment_event(
            claim_id=result["claim_id"], claim_status="mixed",
            assessed_at="2026-10-30T13:00:00+01:00",
            methodology_version="evidence-rules-1.1",
            assessor_type="human_reviewer",
            rationale="Conflicting observations require a mixed assessment.",
        )
        self.assertTrue(event_id.startswith("cin-assessment-"))
        rows = self.db.execute(
            """SELECT claim_status, assessed_at, methodology_version, assessor_type
               FROM cin_claim_assessment_events WHERE claim_id=? ORDER BY assessed_at""",
            (result["claim_id"],),
        ).fetchall()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0][0], first)
        self.assertEqual(tuple(rows[1]), (
            "mixed", "2026-10-30T12:00:00Z", "evidence-rules-1.1", "human_reviewer"
        ))

    def test_assessment_event_rejects_unknown_claim_and_invalid_values(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.repo.append_assessment_event(
                claim_id="missing-claim", claim_status="supported",
                assessed_at="2026-10-30T12:00:00Z",
                methodology_version="method-1", assessor_type="human_reviewer",
                rationale="No matching claim.",
            )
        with self.assertRaises(ValueError):
            self.repo.append_assessment_event(
                claim_id=self.claim["claim_id"], claim_status="verified",
                assessed_at="2026-10-30T12:00:00Z",
                methodology_version="method-1", assessor_type="human_reviewer",
                rationale="Invalid vocabulary.",
            )

    def test_append_observation_preserves_history_and_original_observation(self):
        first = self._store()
        second_id = self.repo.append_observation(
            cin_evidence_id=first["cin_evidence_id"],
            metadata={"metric": "commits", "count": 15},
            observed_at="2026-10-30T13:00:00+01:00",
            source_status="cin_observed",
        )
        rows = self.db.execute(
            """SELECT observation_id, observed_at, retrieved_at, metadata_json, source_status
               FROM cin_evidence_observations WHERE cin_evidence_id=?
               ORDER BY observed_at""",
            (first["cin_evidence_id"],),
        ).fetchall()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["observation_id"], first["observation_id"])
        self.assertEqual(rows[0]["source_status"], "caller_supplied")
        self.assertIsNone(rows[0]["retrieved_at"])
        self.assertEqual(rows[1]["observation_id"], second_id)
        self.assertEqual(rows[1]["observed_at"], "2026-10-30T12:00:00Z")
        self.assertEqual(rows[1]["source_status"], "cin_observed")
        self.assertIn('"count":15', rows[1]["metadata_json"])

    def test_append_observation_rejects_unknown_record_and_nonfinite_json(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.repo.append_observation(
                cin_evidence_id="missing", metadata={}, observed_at="2026-10-30T12:00:00Z",
                source_status="caller_supplied",
            )
        first = self._store()
        with self.assertRaises(ValueError):
            self.repo.append_observation(
                cin_evidence_id=first["cin_evidence_id"], metadata={"n": float("inf")},
                observed_at="2026-10-30T12:00:00Z", source_status="cin_observed",
            )
        self.assertEqual(
            self.db.execute("SELECT COUNT(*) FROM cin_evidence_observations").fetchone()[0],
            1,
        )

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


    def test_repository_rejects_metadata_over_64_kib_before_write(self):
        oversized = {"payload": "x" * (64 * 1024)}
        with self.assertRaisesRegex(ValueError, "65536-byte"):
            self.repo.store_bundle(
                source_namespace="test-provider", evidence_type="caller_metadata",
                metadata=oversized, observed_at="2026-10-30T12:00:00Z",
                claim=self.claim, relationship=self.relationship,
            )
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM cin_evidence_records").fetchone()[0], 0)

    def test_repository_rejects_excessive_depth_and_collection_size(self):
        deeply_nested = {}
        cursor = deeply_nested
        for _ in range(10):
            cursor["child"] = {}
            cursor = cursor["child"]
        for metadata in (deeply_nested, {"items": list(range(257))}):
            with self.subTest(metadata_shape="deep" if metadata is deeply_nested else "wide"):
                with self.assertRaises(ValueError):
                    self.repo.store_bundle(
                        source_namespace="test-provider", evidence_type="caller_metadata",
                        metadata=metadata, observed_at="2026-10-30T12:00:00Z",
                        claim=self.claim, relationship=self.relationship,
                    )
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM cin_evidence_records").fetchone()[0], 0)

    def test_github_source_metadata_rejects_unknown_top_level_and_nested_fields(self):
        base = {
            "symbol": "ETH", "category": "developer_activity",
            "metric": "public_repository_activity_metadata",
            "source_name": "GitHub public repository API",
            "source_url": "https://api.github.com/repos/ethereum/go-ethereum",
            "repository": "ethereum/go-ethereum", "published_at": None,
            "retrieved_at": "2026-10-30T12:00:00Z",
            "measurement_period": "repository metadata snapshot",
            "value": {"default_branch": "main"},
            "unit": "repository metadata fields", "retrieval_status": "success",
            "validation_status": "metadata_shape_validated", "missing_fields": [],
            "freshness_status": "fresh", "freshness_age_seconds": 0,
            "freshness_policy": "seven day freshness window",
            "claim_verification_status": "unverified",
            "independently_verified": False, "provenance": "public GitHub REST API",
            "limitations": ["metadata only"],
        }
        for mutate in (
            lambda item: item.update({"unexpected_secret": "not-allowed"}),
            lambda item: item["value"].update({"unexpected_field": "not-allowed"}),
        ):
            candidate = {**base, "value": dict(base["value"])}
            mutate(candidate)
            with self.subTest(candidate=candidate):
                with self.assertRaisesRegex(ValueError, "allowlist"):
                    self.repo.store_bundle(
                        source_namespace="github_public_repository_api",
                        evidence_type="public_repository_metadata_snapshot",
                        metadata=candidate, observed_at="2026-10-30T12:00:00Z",
                        claim=self.claim, relationship=self.relationship,
                    )
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM cin_evidence_records").fetchone()[0], 0)

    def test_append_observation_applies_repository_byte_limit(self):
        first = self._store()
        with self.assertRaisesRegex(ValueError, "65536-byte"):
            self.repo.append_observation(
                cin_evidence_id=first["cin_evidence_id"],
                metadata={"payload": "x" * (64 * 1024)},
                observed_at="2026-10-30T13:00:00Z",
                source_status="cin_observed",
            )
        self.assertEqual(
            self.db.execute("SELECT COUNT(*) FROM cin_evidence_observations").fetchone()[0],
            1,
        )


if __name__ == "__main__":
    unittest.main()
