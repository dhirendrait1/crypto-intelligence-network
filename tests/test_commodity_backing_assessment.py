from datetime import datetime, timezone

from commodity_backing_assessment import assess_commodity_asset, normalize_evidence


NOW = datetime(2026, 10, 24, tzinfo=timezone.utc)


def valid_item(**overrides):
    item = {
        "evidence_type": "reserve_attestation",
        "source_name": "Example source",
        "source_url": "https://example.com/report",
        "published_at": "2026-10-01T00:00:00Z",
        "checked_at": "2026-10-24T00:00:00Z",
        "status": "verified",
    }
    item.update(overrides)
    return item


def test_missing_evidence_is_not_presented_as_verified():
    result = assess_commodity_asset("PAXG", [], now=NOW)
    assert result["overall_status"] == "evidence_unverified_or_incomplete"
    assert result["not_a_reserve_certification"] is True
    assert all(item["status"] == "unverified" for item in result["evidence_coverage"].values())


def test_verified_metadata_without_required_fields_downgrades():
    result = normalize_evidence(valid_item(source_url=""), now=NOW)
    assert result["status"] == "unverified"
    assert "source_url" in result["missing_fields"]


def test_old_verified_evidence_becomes_stale():
    result = normalize_evidence(
        valid_item(published_at="2026-01-01T00:00:00Z"), now=NOW, max_age_days=90
    )
    assert result["status"] == "stale"


def test_full_evidence_coverage_is_only_metadata_status():
    evidence = [
        valid_item(evidence_type=kind)
        for kind in ("reserve_attestation", "redemption_terms", "custody_or_issuer_disclosure")
    ]
    result = assess_commodity_asset("XAUT", evidence, now=NOW)
    assert result["overall_status"] == "evidence_coverage_complete"
    assert result["not_a_reserve_certification"] is True


def test_future_publication_timestamp_downgrades_supplied_verified_status():
    result = normalize_evidence(
        valid_item(published_at="2026-10-25T00:00:00Z"), now=NOW
    )
    assert result["status"] == "unverified"
    assert "published_at_is_in_the_future" in result["timestamp_validation_errors"]


def test_future_review_timestamp_downgrades_supplied_verified_status():
    result = normalize_evidence(
        valid_item(checked_at="2026-10-25T00:00:00Z"), now=NOW
    )
    assert result["status"] == "unverified"
    assert "checked_at_is_in_the_future" in result["timestamp_validation_errors"]


def test_review_cannot_precede_publication():
    result = normalize_evidence(
        valid_item(
            published_at="2026-10-20T00:00:00Z",
            checked_at="2026-10-19T00:00:00Z",
        ),
        now=NOW,
    )
    assert result["status"] == "unverified"
    assert "checked_at_precedes_published_at" in result["timestamp_validation_errors"]


def test_scheme_only_url_is_not_accepted_as_a_source():
    result = normalize_evidence(valid_item(source_url="https://"), now=NOW)
    assert result["status"] == "unverified"
    assert result["source_url_valid"] is False


def test_embedded_url_credentials_are_not_accepted():
    result = normalize_evidence(
        valid_item(source_url="https://user:secret@example.com/report"), now=NOW
    )
    assert result["status"] == "unverified"
    assert result["source_url_valid"] is False


def test_valid_http_url_and_timestamp_metadata_remain_accepted():
    result = normalize_evidence(valid_item(source_url="http://example.com/report"), now=NOW)
    assert result["status"] == "verified"
    assert result["source_url_valid"] is True
    assert result["timestamp_validation_errors"] == []
