import pytest
from pydantic import ValidationError

from cross_source_evidence_api import (
    CrossSourceComparisonRequest,
    cross_source_evidence_comparison_endpoint,
)


def payload(source, value):
    return {
        "metric": "price",
        "unit": "USD",
        "value": value,
        "source_name": source,
        "source_url": f"https://{source.lower()}.example/price",
        "observed_at": "2026-10-30T10:00:00Z",
    }


def test_endpoint_returns_agreement_and_conflict_without_source_selection():
    request = CrossSourceComparisonRequest(observations=[
        payload("Alpha", 100.0),
        payload("Beta", 105.0),
    ])
    result = cross_source_evidence_comparison_endpoint(request)
    assert result["read_only"] is True
    assert result["not_a_certification"] is True
    assert result["results"][0]["status"] == "conflicting"
    assert result["results"][0]["preferred_source_selected"] is False


def test_endpoint_exposes_agreement_as_limited_corroboration():
    request = CrossSourceComparisonRequest(observations=[
        payload("Alpha", 100.0),
        payload("Beta", 100.5),
    ])
    result = cross_source_evidence_comparison_endpoint(request)
    assert result["results"][0]["confidence_class"] == "limited_corroboration"


def test_request_rejects_empty_or_oversized_observation_batches():
    with pytest.raises(ValidationError):
        CrossSourceComparisonRequest(observations=[])
    with pytest.raises(ValidationError):
        CrossSourceComparisonRequest(observations=[payload("Alpha", 1.0)] * 501)


def test_request_rejects_unknown_fields_and_boolean_window():
    with pytest.raises(ValidationError):
        CrossSourceComparisonRequest(observations=[{**payload("Alpha", 1.0), "extra": True}])
    with pytest.raises(ValidationError):
        CrossSourceComparisonRequest(observations=[payload("Alpha", 1.0)], comparison_window_seconds=True)


def test_request_rejects_invalid_tolerance_ranges():
    with pytest.raises(ValidationError):
        CrossSourceComparisonRequest(observations=[payload("Alpha", 1.0)], relative_tolerance=1.1)
    with pytest.raises(ValidationError):
        CrossSourceComparisonRequest(observations=[payload("Alpha", 1.0)], absolute_tolerance=-1)
