from cin_market_candle_provenance import candle_observation_metadata, market_pair_metadata


def test_coinbase_usd_product_is_not_substituted_for_requested_usdt_pair():
    result = market_pair_metadata("BTCUSDT", "coinbase_public")
    assert result == {
        "source_id": "coinbase_public",
        "base_asset": "BTC",
        "requested_quote_currency": "USDT",
        "quote_currency": None,
        "pair_metadata_status": "quote_mismatch",
    }


def test_coinbase_usd_pair_is_identified_without_substitution():
    result = market_pair_metadata("BTCUSD", "coinbase_public")
    assert result["requested_quote_currency"] == "USD"
    assert result["quote_currency"] == "USD"
    assert result["pair_metadata_status"] == "identified"


def test_binance_and_kraken_keep_requested_quote_currency():
    for source_id in ("binance_public", "kraken_public"):
        result = market_pair_metadata("ETHUSDT", source_id)
        assert result["quote_currency"] == "USDT"
        assert result["requested_quote_currency"] == "USDT"
        assert result["pair_metadata_status"] == "identified"


def test_unknown_pair_does_not_guess_quote_currency():
    result = market_pair_metadata("BTC-EUR", "coinbase_public")
    assert result["quote_currency"] is None
    assert result["pair_metadata_status"] == "unknown"


def test_candle_metadata_does_not_claim_freshness_or_authenticity():
    result = candle_observation_metadata(
        source_id="coinbase_public",
        observed_at="2026-10-28T11:59:00+00:00",
        retrieved_at="2026-10-28T11:59:05+00:00",
        interval="1m",
        quote_currency="USD",
    )
    assert result["timestamp_semantics"] == "candle_close_time"
    assert result["freshness_assessed"] is False
    assert result["source_authenticity_verified"] is False


def test_market_candle_endpoint_includes_provenance_observation_metadata():
    import asyncio
    from unittest.mock import patch
    import cin_public_market_candles_api as market_api

    now_ms = int(market_api.datetime.now(market_api.timezone.utc).timestamp() * 1000)
    rows = [{
        "open_time": now_ms - 120000, "open": 100.0, "high": 102.0,
        "low": 99.0, "close": 101.0, "volume": 5.0,
        "close_time": now_ms - 60001,
        "_source": "Coinbase Exchange public candles API",
        "_source_endpoint": market_api.COINBASE_CANDLES_URL,
    }]
    async def load(*args):
        return rows
    with patch.object(market_api, "_load", side_effect=load):
        result = asyncio.run(market_api.get_market_candles("BTCUSDT", "1m", 5))
    assert result["source_id"] == "coinbase_public"
    assert result["requested_quote_currency"] == "USDT"
    assert result["quote_currency"] is None
    assert result["pair_metadata_status"] == "quote_mismatch"
    observation = result["data"][0]["observation_metadata"]
    assert observation["quote_currency"] is None
    assert observation["timestamp_semantics"] == "candle_close_time"
    assert observation["freshness_assessed"] is False
    assert observation["source_authenticity_verified"] is False
