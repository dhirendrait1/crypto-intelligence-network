"""Focused offline regressions for fallback snapshot request integrity."""
import unittest

import cin_public_market_candles_api as api


def candle(open_time, interval_ms=3_600_000):
    return {
        "open_time": open_time,
        "open": 100.0,
        "high": 102.0,
        "low": 99.0,
        "close": 101.0,
        "volume": 10.0,
        "close_time": open_time + interval_ms - 1,
    }


class FallbackResponseIntegrityTests(unittest.TestCase):
    def test_fallback_symbol_parser_accepts_only_explicit_supported_quote_assets(self):
        self.assertEqual(api._parse_fallback_market_symbol("BTCUSDT", "Coinbase"), ("BTC", "USDT"))
        self.assertEqual(api._parse_fallback_market_symbol("BTCUSD", "Kraken"), ("BTC", "USD"))
        for symbol in ("BTCUSDC", "BTC-EUR", "btcusdt", " BTCUSDT", "BTCUSDT "):
            with self.subTest(symbol=symbol):
                with self.assertRaises(ValueError):
                    api._parse_fallback_market_symbol(symbol, "fallback")

    def test_normalizer_rejects_candle_from_a_different_requested_timeframe(self):
        # This timestamp is a valid hourly open, but not a UTC daily open.
        row = candle(1_700_002_800_000)
        with self.assertRaisesRegex(ValueError, "not aligned"):
            api._normalize_candle_sequence([row], "1d", "kraken")

    def test_normalizer_rejects_close_boundary_that_does_not_match_requested_timeframe(self):
        row = candle(1_700_002_800_000)
        row["close_time"] -= 1
        with self.assertRaisesRegex(ValueError, "do not match"):
            api._normalize_candle_sequence([row], "1h", "kraken")

    def test_snapshot_provenance_rejects_more_rows_than_original_request_limit(self):
        source = "Kraken public OHLC API (fallback after Binance transport failure)"
        rows = []
        for index in range(6):
            row = candle(1_700_002_800_000 + index * 3_600_000)
            row.update({
                "_provider": "kraken",
                "_source": source,
                "_source_endpoint": api.KRAKEN_OHLC_URL,
            })
            rows.append(row)
        with self.assertRaisesRegex(ValueError, "exceeds its valid requested limit"):
            api._validate_provider_snapshot_provenance(
                rows, "kraken", source, api.KRAKEN_OHLC_URL,
                "Binance transport failure", requested_limit=5,
            )

    def test_snapshot_provenance_rejects_mixed_provider_rows(self):
        source = "Kraken public OHLC API (fallback after Binance transport failure)"
        first = candle(1_700_002_800_000)
        second = candle(1_700_006_400_000)
        for row in (first, second):
            row.update({
                "_provider": "kraken",
                "_source": source,
                "_source_endpoint": api.KRAKEN_OHLC_URL,
            })
        second["_provider"] = "coinbase"
        with self.assertRaisesRegex(ValueError, "mixed or mismatched provenance"):
            api._validate_provider_snapshot_provenance(
                [first, second], "kraken", source, api.KRAKEN_OHLC_URL,
                "Binance transport failure", requested_limit=5,
            )


if __name__ == "__main__":
    unittest.main()
