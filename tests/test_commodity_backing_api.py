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


def test_endpoint_rejects_symbols_with_whitespace_or_separator():
    import pytest
    from pydantic import ValidationError

    for symbol in (" PAXG", "PAXG ", "PAXG/USDT"):
        with pytest.raises(ValidationError):
            CommodityBackingAssessmentRequest(symbol=symbol)


def test_endpoint_accepts_zero_day_freshness_threshold():
    request = CommodityBackingAssessmentRequest(symbol="PAXG", max_age_days=0)
    assert request.max_age_days == 0


def test_endpoint_rejects_boolean_freshness_threshold():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        CommodityBackingAssessmentRequest(symbol="PAXG", max_age_days=True)


def test_endpoint_rejects_oversized_evidence_batch():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        CommodityBackingAssessmentRequest(
            symbol="PAXG",
            evidence=[
                {
                    "evidence_type": "reserve_attestation",
                    "source_name": "Example",
                    "source_url": "https://example.com/report",
                    "published_at": "2026-10-01T00:00:00Z",
                    "checked_at": "2026-10-24T00:00:00Z",
                    "status": "unverified",
                }
            ] * 101,
        )


def test_endpoint_rejects_freshness_threshold_above_documented_limit():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        CommodityBackingAssessmentRequest(symbol="PAXG", max_age_days=3651)


def test_endpoint_rejects_symbol_longer_than_documented_limit():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        CommodityBackingAssessmentRequest(symbol="P" * 21)
