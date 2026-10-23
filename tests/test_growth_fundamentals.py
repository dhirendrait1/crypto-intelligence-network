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
         "published_at": "2026-10-01T00:00:00Z", "status": "verified"}
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
        "published_at": "2026-01-01T00:00:00Z", "status": "verified",
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
