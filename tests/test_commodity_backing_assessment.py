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


def test_non_string_timestamps_do_not_raise_or_support_verified_status():
    result = normalize_evidence(
        valid_item(published_at=123, checked_at={"unexpected": "shape"}),
        now=NOW,
    )
    assert result["status"] == "unverified"
    assert "published_at" in result["missing_fields"]
    assert "checked_at" in result["missing_fields"]


def test_naive_timestamps_do_not_support_verified_status():
    result = normalize_evidence(
        valid_item(published_at="2026-10-01T00:00:00", checked_at="2026-10-24T00:00:00"),
        now=NOW,
    )
    assert result["status"] == "unverified"
    assert "published_at" in result["missing_fields"]
    assert "checked_at" in result["missing_fields"]


def test_conflicting_statuses_for_same_evidence_type_are_not_hidden():
    result = assess_commodity_asset(
        "PAXG",
        [
            valid_item(status="verified"),
            valid_item(status="unverified", source_name="Second source"),
        ],
        now=NOW,
    )
    coverage = result["evidence_coverage"]["reserve_attestation"]
    assert coverage["status"] == "conflicting"
    assert coverage["conflict_detected"] is True
    assert result["overall_status"] == "evidence_conflicting_or_incomplete"


def test_non_object_evidence_record_is_retained_as_unverified():
    result = assess_commodity_asset("PAXG", ["not-a-record"], now=NOW)
    assert result["invalid_evidence_record_count"] == 1
    assert result["evidence"][0]["status"] == "unverified"
    assert result["evidence"][0]["invalid_record"] is True


def test_non_list_evidence_input_does_not_raise_or_claim_complete_coverage():
    result = assess_commodity_asset("PAXG", "not-a-list", now=NOW)
    assert result["input_evidence_list_valid"] is False
    assert result["overall_status"] == "evidence_unverified_or_incomplete"
    assert result["evidence"] == []


def test_duplicate_evidence_is_counted_once_in_coverage():
    item = valid_item()
    duplicate = valid_item(source_url="https://example.com/report/")
    result = assess_commodity_asset("PAXG", [item, duplicate], now=NOW)
    coverage = result["evidence_coverage"]["reserve_attestation"]
    assert coverage["evidence_count"] == 1
    assert coverage["duplicate_record_count"] == 1


def test_invalid_freshness_threshold_falls_back_safely():
    result = assess_commodity_asset("PAXG", [valid_item()], now=NOW, max_age_days=-1)
    assert result["freshness_threshold_valid"] is False
    assert result["freshness_threshold_days"] == 90


def test_boolean_and_float_freshness_thresholds_are_not_accepted_as_integers():
    for threshold in (True, 90.0):
        result = assess_commodity_asset("PAXG", [valid_item()], now=NOW, max_age_days=threshold)
        assert result["freshness_threshold_valid"] is False
        assert result["freshness_threshold_days"] == 90


def test_future_publication_has_no_nonnegative_age_claim():
    result = normalize_evidence(
        valid_item(published_at="2026-10-25T00:00:00Z", checked_at="2026-10-25T01:00:00Z"),
        now=NOW,
    )
    assert result["publication_age_days"] is None


def test_invalid_assessment_clock_falls_back_and_is_reported():
    result = assess_commodity_asset("PAXG", [valid_item()], now="not-a-datetime")
    assert result["assessment_clock_valid"] is False
    assert result["evidence"][0]["publication_age_days"] is not None


def test_valid_assessment_clock_is_reported_in_summary_and_rows():
    result = assess_commodity_asset("PAXG", [valid_item()], now=NOW)
    assert result["assessment_clock_valid"] is True
    assert result["evidence"][0]["assessment_clock_valid"] is True


def test_valid_http_url_and_timestamp_metadata_remain_accepted():
    result = normalize_evidence(valid_item(source_url="http://example.com/report"), now=NOW)
    assert result["status"] == "verified"
    assert result["source_url_valid"] is True
    assert result["timestamp_validation_errors"] == []


def test_direct_normalization_rejects_invalid_assessment_clock_safely():
    result = normalize_evidence(valid_item(), now="not-a-datetime")
    assert result["assessment_clock_valid"] is False
    assert result["status"] in {"verified", "unverified"}


def test_timezone_naive_assessment_clock_falls_back_and_is_reported():
    result = assess_commodity_asset("PAXG", [valid_item()], now=NOW.replace(tzinfo=None))
    assert result["assessment_clock_valid"] is False
    assert result["evidence"][0]["assessment_clock_valid"] is False


def test_raw_whitespace_and_control_characters_in_source_urls_are_rejected():
    for url in (
        "https://example.com/report\n.evil",
        "https://example.com/report\t.evil",
        "https://example.com/report with-space",
    ):
        result = normalize_evidence(valid_item(source_url=url), now=NOW)
        assert result["source_url_valid"] is False
        assert result["status"] == "unverified"


def test_invalid_ports_in_source_urls_are_rejected():
    for url in (
        "https://example.com:notaport/report",
        "https://example.com:99999/report",
    ):
        result = normalize_evidence(valid_item(source_url=url), now=NOW)
        assert result["source_url_valid"] is False
        assert result["status"] == "unverified"
