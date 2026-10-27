from cin_monitoring_status import summarize_monitoring_status


def test_all_explicitly_healthy_inputs_are_healthy():
    result = summarize_monitoring_status(health_ok=True, ready=True, provider_ok=True, data_freshness="fresh")
    assert result.status == "healthy"
    assert result.reasons == ()


def test_process_health_does_not_override_stale_market_data():
    result = summarize_monitoring_status(health_ok=True, ready=True, provider_ok=True, data_freshness="stale")
    assert result.status == "degraded"
    assert "market_data_stale" in result.reasons


def test_provider_failure_degrades_but_does_not_claim_service_down():
    result = summarize_monitoring_status(health_ok=True, ready=True, provider_ok=False, data_freshness="fresh")
    assert result.status == "degraded"
    assert result.service_health == "healthy"
    assert result.provider_status == "unhealthy"


def test_failed_health_or_readiness_is_unavailable():
    assert summarize_monitoring_status(health_ok=False, ready=True).status == "unavailable"
    assert summarize_monitoring_status(health_ok=True, ready=False).status == "unavailable"


def test_missing_observations_remain_unknown():
    result = summarize_monitoring_status(health_ok=True, ready=True, provider_ok=None, data_freshness="unverified")
    assert result.status == "unknown"
    assert result.data_freshness == "unknown"
    assert "provider_status_unknown" in result.reasons
    assert "market_data_freshness_unknown" in result.reasons


def test_unrecognized_freshness_never_becomes_fresh():
    result = summarize_monitoring_status(health_ok=True, ready=True, provider_ok=True, data_freshness="")
    assert result.status == "unknown"
    assert result.data_freshness == "unknown"
