import pytest

from cin_source_freshness_policy import FreshnessPolicy, resolve_freshness_policy


def test_default_registry_has_no_unapproved_thresholds():
    assert resolve_freshness_policy("coinbase_public", "market_candles") is None


def test_policy_resolution_requires_exact_source_and_data_type():
    policies = {
        ("coinbase_public", "market_candles"): FreshnessPolicy(
            source_id="coinbase_public",
            data_type="market_candles",
            max_age_seconds=90,
            future_tolerance_seconds=0,
        )
    }
    policy = resolve_freshness_policy(
        "coinbase_public", "market_candles", policies=policies
    )
    assert policy is not None
    assert policy.max_age_seconds == 90
    assert resolve_freshness_policy(
        "kraken_public", "market_candles", policies=policies
    ) is None
    assert resolve_freshness_policy(
        "coinbase_public", "news", policies=policies
    ) is None


@pytest.mark.parametrize("kwargs", [
    {"source_id": "", "data_type": "candles", "max_age_seconds": 60},
    {"source_id": "coinbase", "data_type": "", "max_age_seconds": 60},
    {"source_id": "coinbase", "data_type": "candles", "max_age_seconds": 0},
    {"source_id": "coinbase", "data_type": "candles", "max_age_seconds": True},
    {"source_id": "coinbase", "data_type": "candles", "max_age_seconds": 60,
     "future_tolerance_seconds": -1},
])
def test_policy_rejects_invalid_configuration(kwargs):
    with pytest.raises(ValueError):
        FreshnessPolicy(**kwargs)
