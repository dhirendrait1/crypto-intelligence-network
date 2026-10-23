from datetime import datetime, timezone

from commodity_backing_assessment import assess_commodity_asset, normalize_evidence


NOW = datetime(2026, 10, 24, tzinfo=timezone.utc)


def test_missing_evidence_is_not_presented_as_verified():
    result = assess_commodity_asset("PAXG", [], now=NOW)
    assert result["overall_status"] == "evidence_unverified_or_incomplete"
    assert result["not_a_reserve_certification"] is True
    assert all(item["status"] == "unverified" for item in result["evidence_coverage"].values())


def test_verified_metadata_without_required_fields_downgrades():
    item = {
        "evidence_type": "reserve_attestation",
        "source_name": "Issuer",
        "source_url": "",
        "published_at": "2026-10-01T00:00:00Z",
        "checked_at": "2026-10-24T00:00:00Z",
        "status": "verified",
    }
    result = normalize_evidence(item, now=NOW)
    assert result["status"] == "unverified"
    assert "source_url" in result["missing_fields"]


def test_old_verified_evidence_becomes_stale():
    item = {
        "evidence_type": "reserve_attestation",
        "source_name": "Example source",
        "source_url": "https://example.com/report",
        "published_at": "2026-01-01T00:00:00Z",
        "checked_at": "2026-10-24T00:00:00Z",
        "status": "verified",
    }
    result = normalize_evidence(item, now=NOW, max_age_days=90)
    assert result["status"] == "stale"


def test_full_evidence_coverage_is_only_metadata_status():
    evidence = []
    for kind in ("reserve_attestation", "redemption_terms", "custody_or_issuer_disclosure"):
        evidence.append({
            "evidence_type": kind,
            "source_name": "Example source",
            "source_url": "https://example.com/evidence",
            "published_at": "2026-10-01T00:00:00Z",
            "checked_at": "2026-10-24T00:00:00Z",
            "status": "verified",
        })
    result = assess_commodity_asset("XAUT", evidence, now=NOW)
    assert result["overall_status"] == "evidence_coverage_complete"
    assert result["not_a_reserve_certification"] is True
