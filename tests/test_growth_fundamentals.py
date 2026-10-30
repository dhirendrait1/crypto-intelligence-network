"""Offline tests for CIN growth-fundamentals evidence assessment."""
from datetime import datetime, timezone

from growth_fundamentals_assessment import CATEGORIES, assess_growth_fundamentals
from growth_fundamentals_api import GrowthFundamentalsRequest, growth_fundamentals_assessment_endpoint


def test_empty_evidence_is_incomplete_not_a_quality_score():
    result = assess_growth_fundamentals("eth", [])
    assert result["symbol"] == "ETH"
    assert result["overall_status"] == "evidence_unverified_or_incomplete"
    assert result["evidence_coverage_score"] == 0
    assert result["not_an_investment_recommendation"] is True
    assert result["cin_independently_verified_claims"] is False


def test_complete_metadata_only_counts_coverage_not_certification():
    now = datetime(2026, 10, 24, tzinfo=timezone.utc)
    evidence = [
        {"category": category, "source_name": "Example source",
         "source_url": "https://example.com/evidence",
         "published_at": "2026-10-01T00:00:00Z", "checked_at": "2026-10-20T00:00:00Z", "status": "verified"}
        for category in CATEGORIES
    ]
    result = assess_growth_fundamentals("ETH", evidence, now=now)
    assert result["evidence_coverage_score"] == 100
    assert result["overall_status"] == "evidence_coverage_complete"
    assert result["cin_independently_verified_claims"] is False
    assert all(row["cin_independently_verified"] is False for row in result["evidence"])


def test_missing_source_url_downgrades_verified_record():
    result = assess_growth_fundamentals("ABC", [{
        "category": "token_utility", "source_name": "Example",
        "published_at": "2026-10-01T00:00:00Z", "status": "verified",
    }])
    assert result["evidence"][0]["status"] == "unverified"
    assert "source_url" in result["evidence"][0]["missing_fields"]


def test_old_evidence_becomes_stale():
    now = datetime(2026, 10, 24, tzinfo=timezone.utc)
    result = assess_growth_fundamentals("ABC", [{
        "category": "developer_activity", "source_name": "Example",
        "source_url": "https://example.com/dev",
        "published_at": "2026-01-01T00:00:00Z", "checked_at": "2026-10-20T00:00:00Z", "status": "verified",
    }], now=now, max_age_days=90)
    assert result["evidence"][0]["status"] == "stale"
    assert result["overall_status"] == "evidence_stale_or_incomplete"


def test_api_marks_caller_supplied_metadata():
    result = growth_fundamentals_assessment_endpoint(
        GrowthFundamentalsRequest(symbol="eth", evidence=[])
    )
    assert result["symbol"] == "ETH"
    assert result["mode"] == "read_only"
    assert result["evidence_source_mode"] == "caller_supplied_metadata"
    assert result["source_documents_fetched_by_cin"] is False


def test_verified_growth_evidence_requires_valid_check_timestamp():
    now = datetime(2026, 10, 24, tzinfo=timezone.utc)
    result = assess_growth_fundamentals("ABC", [{
        "category": "token_utility", "source_name": "Example",
        "source_url": "https://example.com/utility",
        "published_at": "2026-10-01T00:00:00Z", "status": "verified",
    }], now=now)
    row = result["evidence"][0]
    assert row["status"] == "unverified"
    assert "checked_at" in row["missing_fields"]


def test_growth_evidence_rejects_future_or_impossible_check_chronology():
    now = datetime(2026, 10, 24, tzinfo=timezone.utc)
    base = {
        "category": "token_utility", "source_name": "Example",
        "source_url": "https://example.com/utility",
        "published_at": "2026-10-10T00:00:00Z", "status": "verified",
    }
    future = assess_growth_fundamentals("ABC", [{**base, "checked_at": "2026-10-25T00:00:00Z"}], now=now)
    reversed_time = assess_growth_fundamentals("ABC", [{**base, "checked_at": "2026-10-09T00:00:00Z"}], now=now)
    assert future["evidence"][0]["status"] == "unverified"
    assert "checked_at_is_in_the_future" in future["evidence"][0]["timestamp_validation_errors"]
    assert reversed_time["evidence"][0]["status"] == "unverified"
    assert "checked_at_precedes_published_at" in reversed_time["evidence"][0]["timestamp_validation_errors"]


def test_growth_evidence_source_role_and_fingerprint_are_explicit():
    record = {
        "category": "security_and_audits", "evidence_id": "audit-001",
        "source_role": "auditor", "source_name": "Example Auditor",
        "source_url": "https://example.com/audit",
        "published_at": "2026-10-01T00:00:00Z",
        "checked_at": "2026-10-20T00:00:00Z", "status": "verified",
    }
    result = assess_growth_fundamentals("ABC", [record], now=datetime(2026, 10, 24, tzinfo=timezone.utc))
    row = result["evidence"][0]
    assert row["evidence_id"] == "audit-001"
    assert row["source_role"] == "auditor"
    assert row["source_role_is_self_reported"] is True
    assert row["source_role_authenticated"] is False
    assert len(row["record_fingerprint_sha256"]) == 64
    assert row["fingerprint_is_authenticity_proof"] is False


def test_growth_evidence_fingerprint_changes_when_claim_metadata_changes():
    from copy import deepcopy
    base = {
        "category": "token_utility", "evidence_id": "utility-1",
        "source_name": "Example", "source_role": "issuer",
        "source_url": "https://example.com/utility",
        "published_at": "2026-10-01T00:00:00Z",
        "checked_at": "2026-10-20T00:00:00Z", "status": "unverified",
        "notes": "Initial issuer statement",
    }
    changed = deepcopy(base)
    changed["notes"] = "Revised issuer statement"
    now = datetime(2026, 10, 24, tzinfo=timezone.utc)
    first = assess_growth_fundamentals("ABC", [base], now=now)["evidence"][0]
    second = assess_growth_fundamentals("ABC", [changed], now=now)["evidence"][0]
    assert first["record_fingerprint_sha256"] != second["record_fingerprint_sha256"]



def test_growth_claim_text_is_separate_from_evidence_and_fingerprinted():
    now = datetime(2026, 10, 24, tzinfo=timezone.utc)
    record = {
        "category": "fees_and_revenue", "evidence_id": "claim-7",
        "source_role": "issuer", "claim_text": "Protocol revenue increased 20% quarter over quarter.",
        "source_name": "Project issuer", "source_url": "https://example.com/report",
        "published_at": "2026-10-01T00:00:00Z", "checked_at": "2026-10-20T00:00:00Z",
        "status": "unverified",
    }
    row = assess_growth_fundamentals("ABC", [record], now=now)["evidence"][0]
    assert row["claim_text"] == record["claim_text"]
    assert row["claim_text_is_caller_supplied"] is True
    assert row["cin_independently_verified"] is False
    changed = {**record, "claim_text": "Protocol revenue increased 30% quarter over quarter."}
    changed_row = assess_growth_fundamentals("ABC", [changed], now=now)["evidence"][0]
    assert row["record_fingerprint_sha256"] != changed_row["record_fingerprint_sha256"]


def test_growth_claim_is_linked_as_context_only_and_not_assessed_as_true():
    now = datetime(2026, 10, 24, tzinfo=timezone.utc)
    row = assess_growth_fundamentals("ABC", [{
        "category": "fees_and_revenue", "evidence_id": "revenue-report-1",
        "claim_text": "Protocol revenue increased 20% quarter over quarter.",
        "source_name": "Project issuer", "source_url": "https://example.com/report",
        "published_at": "2026-10-01T00:00:00Z", "checked_at": "2026-10-20T00:00:00Z",
        "status": "unverified",
    }], now=now)["evidence"][0]
    claim = row["claim"]
    relationship = row["claim_evidence_relationship"]
    assert claim["subject"] == "ABC"
    assert claim["predicate"] == "fees_and_revenue"
    assert claim["claim_status"] == "not_assessed"
    assert claim["claim_id_is_truth_proof"] is False
    assert relationship["claim_id"] == claim["claim_id"]
    assert relationship["evidence_id"] == "revenue-report-1"
    assert relationship["relationship"] == "context_only"
    assert relationship["review_status"] == "automated_candidate"
    assert relationship["relationship_is_persisted"] is False


def test_growth_claim_without_evidence_id_is_not_linked():
    now = datetime(2026, 10, 24, tzinfo=timezone.utc)
    row = assess_growth_fundamentals("ABC", [{
        "category": "token_utility",
        "claim_text": "The token is required for protocol access.",
    }], now=now)["evidence"][0]
    assert row["claim"] is not None
    assert row["claim_evidence_relationship"] is None


def test_growth_evidence_without_claim_text_has_no_claim_object():
    now = datetime(2026, 10, 24, tzinfo=timezone.utc)
    row = assess_growth_fundamentals("ABC", [{
        "category": "token_utility", "evidence_id": "utility-1",
    }], now=now)["evidence"][0]
    assert row["claim"] is None
    assert row["claim_evidence_relationship"] is None


def test_growth_claim_is_linked_as_context_only_without_verification():
    now = datetime(2026, 10, 24, tzinfo=timezone.utc)
    record = {
        "category": "fees_and_revenue", "evidence_id": "revenue-report-9",
        "claim_text": "Protocol revenue increased 20% quarter over quarter.",
        "source_name": "Project issuer", "source_url": "https://example.com/report",
        "published_at": "2026-10-01T00:00:00Z", "checked_at": "2026-10-20T00:00:00Z",
        "status": "unverified",
    }
    row = assess_growth_fundamentals("ABC", [record], now=now)["evidence"][0]
    claim = row["claim"]
    link = row["claim_evidence_relationship"]
    assert claim["subject"] == "ABC"
    assert claim["predicate"] == "fees_and_revenue"
    assert claim["claim_status"] == "not_assessed"
    assert claim["claim_id_is_truth_proof"] is False
    assert link["claim_id"] == claim["claim_id"]
    assert link["evidence_id"] == "revenue-report-9"
    assert link["relationship"] == "context_only"
    assert link["review_status"] == "automated_candidate"
    assert link["relationship_is_persisted"] is False


def test_growth_claim_without_evidence_id_is_not_linked():
    now = datetime(2026, 10, 24, tzinfo=timezone.utc)
    record = {
        "category": "fees_and_revenue",
        "claim_text": "Caller supplied claim.",
        "source_name": "Example", "source_url": "https://example.com/report",
        "published_at": "2026-10-01T00:00:00Z", "checked_at": "2026-10-20T00:00:00Z",
        "status": "unverified",
    }
    row = assess_growth_fundamentals("ABC", [record], now=now)["evidence"][0]
    assert row["claim"] is not None
    assert row["claim_evidence_relationship"] is None


def test_growth_evidence_without_claim_text_has_no_claim_objects():
    now = datetime(2026, 10, 24, tzinfo=timezone.utc)
    record = {
        "category": "fees_and_revenue", "evidence_id": "evidence-1",
        "source_name": "Example", "source_url": "https://example.com/report",
        "published_at": "2026-10-01T00:00:00Z", "checked_at": "2026-10-20T00:00:00Z",
        "status": "unverified",
    }
    row = assess_growth_fundamentals("ABC", [record], now=now)["evidence"][0]
    assert row["claim"] is None
    assert row["claim_evidence_relationship"] is None
