"""Offline tests for the CIN commodity backing API endpoint."""
from commodity_backing_api import (
    CommodityBackingAssessmentRequest,
    commodity_backing_assessment_endpoint,
)


def test_endpoint_returns_unverified_for_empty_evidence():
    result = commodity_backing_assessment_endpoint(
        CommodityBackingAssessmentRequest(symbol="PAXG")
    )
    assert result["symbol"] == "PAXG"
    assert result["overall_status"] == "evidence_unverified_or_incomplete"
    assert result["mode"] == "read_only"
    assert result["not_a_reserve_certification"] is True
    assert result["evidence_source_mode"] == "caller_supplied_metadata"
    assert result["source_documents_fetched_by_cin"] is False


def test_endpoint_normalizes_supplied_evidence_and_preserves_caveats():
    result = commodity_backing_assessment_endpoint(
        CommodityBackingAssessmentRequest(
            symbol="xaut",
            evidence=[
                {
                    "evidence_type": "reserve_attestation",
                    "source_name": "Example issuer",
                    "source_url": "https://example.com/reserves",
                    "published_at": "2026-10-01T00:00:00Z",
                    "checked_at": "2026-10-24T00:00:00Z",
                    "status": "verified",
                }
            ],
        )
    )
    assert result["symbol"] == "XAUT"
    assert result["evidence"][0]["status"] == "verified"
    assert result["evidence_coverage"]["reserve_attestation"]["status"] == "verified"
    assert result["evidence_coverage"]["redemption_terms"]["status"] == "unverified"
    assert result["not_a_reserve_certification"] is True


def test_endpoint_stale_threshold_is_configurable():
    result = commodity_backing_assessment_endpoint(
        CommodityBackingAssessmentRequest(
            symbol="PAXG",
            max_age_days=30,
            evidence=[
                {
                    "evidence_type": "reserve_attestation",
                    "source_name": "Example issuer",
                    "source_url": "https://example.com/reserves",
                    "published_at": "2026-08-01T00:00:00Z",
                    "checked_at": "2026-10-24T00:00:00Z",
                    "status": "verified",
                }
            ],
        )
    )
    assert result["evidence"][0]["status"] == "stale"
