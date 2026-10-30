"""Offline contract tests for the shared CIN claim/evidence model."""
from datetime import datetime, timezone

import pytest

from cin_verifiable_evidence import (
    CLAIM_STATUSES, RELATIONSHIPS, REVIEW_STATUSES,
    create_claim, create_claim_evidence_relationship,
)

NOW = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)


def test_claim_id_is_deterministic_and_created_time_is_not_identity():
    first = create_claim(subject="ETH", predicate="protocol_fee_revenue",
                         statement="Revenue increased", value=12, unit="USD",
                         created_at=NOW)
    second = create_claim(subject="ETH", predicate="protocol_fee_revenue",
                          statement="Revenue increased", value=12, unit="USD",
                          created_at=datetime(2026, 10, 31, tzinfo=timezone.utc))
    assert first["claim_id"] == second["claim_id"]
    assert first["created_at"] != second["created_at"]
    assert first["claim_id_is_truth_proof"] is False


def test_claim_identity_changes_when_bounded_statement_changes():
    first = create_claim(subject="ETH", predicate="protocol_fee_revenue",
                         statement="Revenue increased")
    second = create_claim(subject="ETH", predicate="protocol_fee_revenue",
                          statement="Revenue doubled")
    assert first["claim_id"] != second["claim_id"]


def test_claim_supports_typed_values_and_valid_time():
    claim = create_claim(subject="ETH", predicate="protocol_fee_revenue",
                         statement="Revenue was measured", value=42.5, unit="USD",
                         valid_time_start=NOW, valid_time_end=NOW,
                         claim_status="insufficient_evidence", created_at=NOW)
    assert claim["value"] == 42.5
    assert claim["unit"] == "USD"
    assert claim["claim_status"] == "insufficient_evidence"


@pytest.mark.parametrize("kwargs", [
    {"subject": "", "predicate": "x", "statement": "y"},
    {"subject": "ETH", "predicate": "", "statement": "y"},
    {"subject": "ETH", "predicate": "x", "statement": ""},
    {"subject": "ETH", "predicate": "x", "statement": "y", "claim_status": "verified"},
    {"subject": "ETH", "predicate": "x", "statement": "y", "claim_status": []},
    {"subject": "ETH", "predicate": "x", "statement": "y", "created_at": datetime(2026, 1, 1)},
    {"subject": "ETH", "predicate": "x", "statement": "y", "value": float("nan")},
    {"subject": "ETH", "predicate": "x", "statement": "y",
     "valid_time_start": datetime(2026, 2, 1, tzinfo=timezone.utc),
     "valid_time_end": datetime(2026, 1, 1, tzinfo=timezone.utc)},
])
def test_claim_rejects_invalid_required_fields_status_times_and_values(kwargs):
    with pytest.raises(ValueError):
        create_claim(**kwargs)


def test_all_claim_statuses_are_explicitly_supported():
    for status in CLAIM_STATUSES:
        assert create_claim(subject="ETH", predicate="test", statement="Claim",
                            claim_status=status)["claim_status"] == status


def test_relationship_object_preserves_claim_and_evidence_identity():
    link = create_claim_evidence_relationship(
        claim_id="cin-claim-1", evidence_id="evidence-1",
        relationship="contradicts", rationale="The evidence reports a different value",
        review_status="human_reviewed", created_at=NOW,
    )
    assert link["relationship"] == "contradicts"
    assert link["review_status"] == "human_reviewed"
    assert link["relationship_is_persisted"] is False


@pytest.mark.parametrize("relationship", sorted(RELATIONSHIPS))
def test_all_relationship_types_are_supported(relationship):
    assert create_claim_evidence_relationship(
        claim_id="claim-1", evidence_id="evidence-1",
        relationship=relationship, rationale="Relevant evidence",
    )["relationship"] == relationship


@pytest.mark.parametrize("review_status", sorted(REVIEW_STATUSES))
def test_all_review_states_are_supported(review_status):
    assert create_claim_evidence_relationship(
        claim_id="claim-1", evidence_id="evidence-1",
        relationship="supports", rationale="Relevant evidence",
        review_status=review_status,
    )["review_status"] == review_status


@pytest.mark.parametrize("kwargs", [
    {"claim_id": "", "evidence_id": "e1", "relationship": "supports", "rationale": "x"},
    {"claim_id": "c1", "evidence_id": "", "relationship": "supports", "rationale": "x"},
    {"claim_id": "c1", "evidence_id": "e1", "relationship": "unknown", "rationale": "x"},
    {"claim_id": "c1", "evidence_id": "e1", "relationship": [], "rationale": "x"},
    {"claim_id": "c1", "evidence_id": "e1", "relationship": "supports", "rationale": "x", "review_status": []},
    {"claim_id": "c1", "evidence_id": "e1", "relationship": "supports", "rationale": ""},
    {"claim_id": "c1", "evidence_id": "e1", "relationship": "supports", "rationale": "x", "review_status": "approved"},
    {"claim_id": "c1", "evidence_id": "e1", "relationship": "supports", "rationale": "x",
     "created_at": datetime(2026, 1, 1)},
])
def test_relationship_rejects_invalid_ids_types_rationale_and_timestamps(kwargs):
    with pytest.raises(ValueError):
        create_claim_evidence_relationship(**kwargs)
