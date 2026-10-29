"""Deterministic provenance metadata helpers for CIN public market candles."""
from __future__ import annotations

import re
from typing import Any


def market_pair_metadata(symbol: str, source_id: str) -> dict[str, Any]:
    """Describe the requested and provider-compatible pair without guessing."""
    normalized = symbol.strip().upper()
    match = re.fullmatch(r"([A-Z0-9]+)(USDT|USD)", normalized)
    if not match:
        return {
            "source_id": source_id,
            "base_asset": None,
            "requested_quote_currency": None,
            "quote_currency": None,
            "pair_metadata_status": "unknown",
        }

    base_asset, requested_quote = match.groups()
    quote_mismatch = source_id == "coinbase_public" and requested_quote != "USD"
    actual_quote = None if quote_mismatch else requested_quote
    return {
        "source_id": source_id,
        "base_asset": base_asset,
        "requested_quote_currency": requested_quote,
        "quote_currency": actual_quote,
        "pair_metadata_status": "quote_mismatch" if quote_mismatch else "identified",
    }


def candle_observation_metadata(*, source_id: str, observed_at: str, retrieved_at: str,
                                interval: str, quote_currency: str | None,
                                timestamp_semantics: str = "candle_close_time") -> dict[str, Any]:
    """Label observation metadata; do not claim source authenticity or freshness validation."""
    return {
        "source_id": source_id,
        "observed_at": observed_at,
        "retrieved_at": retrieved_at,
        "timestamp_semantics": timestamp_semantics,
        "interval": interval,
        "quote_currency": quote_currency,
        "freshness_assessed": False,
        "source_authenticity_verified": False,
    }
