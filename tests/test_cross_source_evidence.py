from cross_source_evidence import compare_metric_observations


def observation(source, value, **overrides):
    item = {
        "metric": "price",
        "unit": "USD",
        "value": value,
        "source_name": source,
        "source_url": f"https://{source.lower()}.example/market",
        "observed_at": "2026-10-30T10:00:00Z",
    }
    item.update(overrides)
    return item


def test_two_sources_within_tolerance_are_limited_corroboration_not_certification():
    result = compare_metric_observations([
        observation("Alpha", 100.0),
        observation("Beta", 100.5),
    ])
    item = result["results"][0]
    assert item["status"] == "agreement_observed"
    assert item["confidence_class"] == "limited_corroboration"
    assert item["comparable_source_count"] == 2
    assert item["source_independence_verified"] is False
    assert item["preferred_source_selected"] is False
    assert result["read_only"] is True
    assert result["not_a_certification"] is True


def test_material_source_disagreement_is_exposed_without_selecting_a_winner():
    result = compare_metric_observations([
        observation("Alpha", 100.0),
        observation("Beta", 110.0),
    ])
    item = result["results"][0]
    assert item["status"] == "conflicting"
    assert item["confidence_class"] == "low_confidence_conflict"
    assert item["value_min"] == 100.0
    assert item["value_max"] == 110.0
    assert item["preferred_source_selected"] is False
    assert len(item["source_observations"]) == 2


def test_duplicate_source_urls_do_not_count_as_multiple_sources():
    result = compare_metric_observations([
        observation("Alpha", 100.0),
        observation("Alpha mirror", 100.1, source_url="https://alpha.example/market/"),
    ])
    item = result["results"][0]
    assert item["status"] == "insufficient_independent_source_count"
    assert item["comparable_source_count"] == 1
    assert item["duplicate_source_observation_count"] == 1


def test_observations_outside_time_window_are_not_compared():
    result = compare_metric_observations([
        observation("Alpha", 100.0),
        observation("Beta", 120.0, observed_at="2026-10-30T10:10:00Z"),
    ], comparison_window_seconds=300)
    item = result["results"][0]
    assert item["status"] == "insufficient_independent_source_count"
    assert item["observations_outside_time_window_count"] == 1


def test_different_units_are_never_combined():
    result = compare_metric_observations([
        observation("Alpha", 100.0, unit="USD"),
        observation("Beta", 100.0, unit="USDT"),
    ])
    assert result["metric_group_count"] == 2
    assert all(item["status"] == "insufficient_independent_source_count" for item in result["results"])


def test_invalid_observations_are_counted_not_silently_used():
    result = compare_metric_observations([
        observation("Alpha", True),
        observation("Beta", float("nan")),
        observation("Gamma", 100.0, observed_at="not-a-time"),
        observation("Delta", 101.0),
    ])
    assert result["rejected_observation_count"] == 3
    assert result["results"][0]["status"] == "insufficient_independent_source_count"


def test_comparison_rejects_invalid_tolerance_contracts():
    import pytest

    with pytest.raises(ValueError, match="absolute_tolerance"):
        compare_metric_observations([], absolute_tolerance=-1)
    with pytest.raises(ValueError, match="relative_tolerance"):
        compare_metric_observations([], relative_tolerance=float("inf"))
    with pytest.raises(ValueError, match="comparison_window_seconds"):
        compare_metric_observations([], comparison_window_seconds=True)


def test_exact_tolerance_boundary_is_agreement():
    result = compare_metric_observations([
        observation("Alpha", 100.0),
        observation("Beta", 101.0),
    ], relative_tolerance=0.01)
    assert result["results"][0]["status"] == "agreement_observed"


def test_latest_observation_per_source_is_used_for_comparison():
    result = compare_metric_observations([
        observation("Alpha", 100.0, observed_at="2026-10-30T10:00:00Z"),
        observation("Alpha latest", 104.0, source_url="https://alpha.example/market/",
                    observed_at="2026-10-30T10:04:00Z"),
        observation("Beta", 104.0, observed_at="2026-10-30T10:04:00Z"),
    ], comparison_window_seconds=300, relative_tolerance=0.01)

    item = result["results"][0]
    assert item["status"] == "agreement_observed"
    assert item["comparable_source_count"] == 2
    assert item["duplicate_source_observation_count"] == 1
    alpha = next(row for row in item["source_observations"] if row["source_url"] == "https://alpha.example")
    assert alpha["value"] == 104.0
    assert alpha["observed_at"] == "2026-10-30T10:04:00+00:00"


def test_different_paths_on_same_origin_do_not_count_as_separate_sources():
    result = compare_metric_observations([
        observation("Alpha market page", 100.0, source_url="https://alpha.example/markets/btc"),
        observation("Alpha API endpoint", 100.1, source_url="https://alpha.example/api/v1/btc"),
        observation("Beta", 100.0),
    ])

    item = result["results"][0]
    assert item["status"] == "agreement_observed"
    assert item["comparable_source_count"] == 2
    assert item["duplicate_source_observation_count"] == 1
    assert {row["source_url"] for row in item["source_observations"]} == {
        "https://alpha.example",
        "https://beta.example",
    }



def test_http_and_https_variants_of_same_host_are_one_source():
    result = compare_metric_observations([
        observation("Alpha secure", 100.0, source_url="https://alpha.example/price"),
        observation("Alpha legacy", 100.0, source_url="http://alpha.example/quote"),
        observation("Beta", 100.0),
    ])

    item = result["results"][0]
    assert item["comparable_source_count"] == 2
    assert item["duplicate_source_observation_count"] == 1
    assert {row["source_url"] for row in item["source_observations"]} == {
        "alpha.example",
        "beta.example",
    }
