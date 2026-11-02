from cin_dashboard_state import normalize_dashboard_state


def test_unrequested_capability_is_unavailable():
    result = normalize_dashboard_state(capability_available=False)
    assert result.state == "unavailable"


def test_failed_refresh_is_error_and_keeps_prior_data_labelled():
    previous = [{"price": 100}]
    result = normalize_dashboard_state(data=previous, response_received=False, error_code="provider_timeout")
    assert result.state == "error"
    assert result.data is previous
    assert result.error_code == "provider_timeout"


def test_missing_response_is_loading_not_empty():
    assert normalize_dashboard_state().state == "loading"


def test_successful_empty_list_is_empty():
    result = normalize_dashboard_state(data=[], response_received=True)
    assert result.state == "empty"


def test_unknown_data_is_not_coerced_to_zero():
    result = normalize_dashboard_state(data={"price": None}, response_received=True)
    assert result.state == "ready"
    assert result.data == {"price": None}


def test_stale_takes_precedence_over_partial():
    result = normalize_dashboard_state(data=[1], response_received=True, freshness="stale", partial=True)
    assert result.state == "stale"


def test_partial_result_is_explicit():
    result = normalize_dashboard_state(data=[1], response_received=True, partial=True, warnings=["one source missing"])
    assert result.state == "partial"
    assert result.warnings == ("one source missing",)


def test_unknown_freshness_and_missing_provenance_remain_unknown():
    result = normalize_dashboard_state(data=[1], response_received=True, freshness="garbage")
    assert result.freshness == "unknown"
    assert result.source is None
    assert result.observed_at is None
    assert result.retrieved_at is None


def test_provenance_strings_are_trimmed_without_fabrication():
    result = normalize_dashboard_state(
        data=[1], response_received=True, source=" Coinbase ",
        observed_at=" 2026-10-28T00:00:00Z ", retrieved_at=" 2026-10-28T00:00:02Z ",
    )
    assert result.source == "Coinbase"
    assert result.observed_at == "2026-10-28T00:00:00Z"
    assert result.retrieved_at == "2026-10-28T00:00:02Z"


def test_error_state_has_priority_over_unavailable():
    result = normalize_dashboard_state(capability_available=False, error_code="request_failed")
    assert result.state == "error"
