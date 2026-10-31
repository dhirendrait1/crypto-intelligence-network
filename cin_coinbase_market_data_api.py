"""Read-only HTTP API for explicitly identified Coinbase USD candle markets."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query

try:
    from cin_coinbase_public_market_data import (
        GRANULARITIES,
        fetch_candles_with_diagnostics,
    )
except ModuleNotFoundError as exc:
    if exc.name != "cin_coinbase_public_market_data":
        raise
    from app.cin_coinbase_public_market_data import GRANULARITIES, fetch_candles_with_diagnostics

router = APIRouter(tags=["coinbase-public-market-data"])


def _utc(timestamp_seconds: int) -> str:
    return datetime.fromtimestamp(timestamp_seconds, timezone.utc).isoformat()


@router.get("/coinbase/market-candles")
async def get_coinbase_market_candles(
    product_id: str = Query(default="BTC-USD", min_length=6, max_length=16),
    granularity: str = Query(default="1h"),
    start: int = Query(..., ge=0),
    end: int = Query(..., gt=0),
) -> dict[str, Any]:
    """Return bounded public Coinbase candles with explicit source provenance."""
    if granularity not in GRANULARITIES:
        raise HTTPException(status_code=400, detail="Unsupported Coinbase candle granularity.")
    try:
        rows, provider_diagnostics = await asyncio.to_thread(fetch_candles_with_diagnostics, product_id, granularity, start, end)
    except ValueError as exc:
        # Validation messages are controlled by the local adapter, not provider payloads.
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        # Keep provider response bodies and exception details out of the public API.
        raise HTTPException(status_code=503, detail="Coinbase public market-data provider is temporarily unavailable.") from exc

    retrieved_at = datetime.now(timezone.utc)
    now_ms = int(retrieved_at.timestamp() * 1000)
    duration_ms = GRANULARITIES[granularity] * 1000
    closed_rows = [row for row in rows if row["close_time"] < now_ms]
    latest_closed = closed_rows[-1] if closed_rows else None
    latest_age = round((now_ms - latest_closed["close_time"]) / 1000, 3) if latest_closed else None
    stale_threshold = duration_ms * 2 / 1000
    return {
        "service": "cin",
        "mode": "read_only",
        "source": "Coinbase Exchange public candles API",
        "source_endpoint": "https://api.exchange.coinbase.com/products/{product_id}/candles",
        "product_id": product_id,
        "quote_currency": "USD",
        "granularity": granularity,
        "requested_start_utc": _utc(start),
        "requested_end_utc": _utc(end),
        "retrieved_at": retrieved_at.isoformat(),
        "count": len(rows),
        **provider_diagnostics,
        "provider_window_coverage": "not_established",
        "latest_closed_candle_close_time_utc": (
            datetime.fromtimestamp(latest_closed["close_time"] / 1000, timezone.utc).isoformat()
            if latest_closed else None
        ),
        "latest_closed_candle_age_seconds": latest_age,
        "stale_threshold_seconds": stale_threshold,
        "stale_data_warning": (
            "Latest completed candle is older than the two-interval freshness threshold."
            if latest_age is not None and latest_age > stale_threshold else None
        ),
        "data": [
            {
                **row,
                "open_time_utc": datetime.fromtimestamp(row["open_time"] / 1000, timezone.utc).isoformat(),
                "close_time_utc": datetime.fromtimestamp(row["close_time"] / 1000, timezone.utc).isoformat(),
                "is_closed": row["close_time"] < now_ms,
            }
            for row in rows
        ],
        "limitations": [
            "Public exchange-provided data; not independently audited by CIN.",
            "Only explicitly USD-quoted Coinbase products are accepted; quote currencies are not converted.",
            "The latest candle may still be forming.",
            "Provider row accounting describes the returned payload only; requested-window coverage is not established by this endpoint.",
            "No account endpoints, credentials, orders, wallets, or trade execution are used.",
        ],
    }
