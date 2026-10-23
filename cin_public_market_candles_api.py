"""Read-only public OHLC candles and live technical analysis from Binance public market data.

This module uses public market-data endpoints only: no credentials, account access,
order placement, or trade execution. Data provenance is included in every response.
"""
from __future__ import annotations

import asyncio
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query

try:
    from app.cin_technical_analysis import analyze_ohlc
except ModuleNotFoundError:
    from cin_technical_analysis import analyze_ohlc

router = APIRouter(tags=["public-market-candles"])
BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"
TIMEFRAMES = {"1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w", "1M"}


def _fetch_klines(symbol: str, interval: str, limit: int) -> list[dict[str, Any]]:
    query = urllib.parse.urlencode({"symbol": symbol, "interval": interval, "limit": limit})
    request = urllib.request.Request(
        f"{BINANCE_KLINES_URL}?{query}",
        headers={"accept": "application/json", "user-agent": "CIN-Research-API/0.1.0"},
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        if response.status != 200:
            raise RuntimeError(f"Provider returned HTTP {response.status}")
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Provider response was not a list")
    candles = []
    for row in payload:
        if not isinstance(row, list) or len(row) < 7:
            continue
        try:
            candles.append({
                "open_time": int(row[0]),
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "volume": float(row[5]),
                "close_time": int(row[6]),
            })
        except (TypeError, ValueError, OverflowError):
            continue
    if not candles:
        raise ValueError("Provider returned no valid candles")
    return candles


async def _load(symbol: str, interval: str, limit: int) -> list[dict[str, Any]]:
    try:
        return await asyncio.to_thread(_fetch_klines, symbol, interval, limit)
    except urllib.error.HTTPError as exc:
        if exc.code == 429 or exc.code == 418:
            raise HTTPException(status_code=503, detail="Public market-data rate limit reached; retry later.") from exc
        raise HTTPException(status_code=502, detail=f"Public market-data provider returned HTTP {exc.code}.") from exc
    except (urllib.error.URLError, TimeoutError, OSError):
        raise HTTPException(status_code=503, detail="Public market-data provider is temporarily unavailable.") from None
    except (ValueError, json.JSONDecodeError):
        raise HTTPException(status_code=502, detail="Public market-data provider returned an invalid response.") from None


def _validate(symbol: str, interval: str, limit: int) -> str:
    normalized = symbol.strip().upper()
    if not re.fullmatch(r"[A-Z0-9]{5,20}", normalized):
        raise HTTPException(status_code=400, detail="Symbol must be a trading pair such as BTCUSDT.")
    if interval not in TIMEFRAMES:
        raise HTTPException(status_code=400, detail="Unsupported interval. Use a supported Binance kline interval.")
    if not 5 <= limit <= 500:
        raise HTTPException(status_code=400, detail="Limit must be between 5 and 500.")
    return normalized


@router.get("/market-candles")
async def get_market_candles(
    symbol: str = Query(default="BTCUSDT", min_length=5, max_length=20),
    interval: str = Query(default="1h"),
    limit: int = Query(default=100, ge=5, le=500),
) -> dict[str, Any]:
    """Retrieve timestamped public OHLCV candles with source provenance."""
    normalized = _validate(symbol, interval, limit)
    rows = await _load(normalized, interval, limit)
    return {
        "service": "cin",
        "mode": "read_only",
        "source": "Binance public market-data API",
        "source_endpoint": BINANCE_KLINES_URL,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "symbol": normalized,
        "timeframe": interval,
        "count": len(rows),
        "data": [
            {
                **row,
                "open_time_utc": datetime.fromtimestamp(row["open_time"] / 1000, timezone.utc).isoformat(),
                "close_time_utc": datetime.fromtimestamp(row["close_time"] / 1000, timezone.utc).isoformat(),
            }
            for row in rows
        ],
        "limitations": [
            "Public exchange-provided market data; not independently audited by CIN.",
            "The latest candle may still be forming.",
            "No account endpoints, API keys, orders, or trade execution are used.",
        ],
    }


@router.get("/technical-analysis/market")
async def analyze_public_market(
    symbol: str = Query(default="BTCUSDT", min_length=5, max_length=20),
    interval: str = Query(default="1h"),
    limit: int = Query(default=100, ge=5, le=500),
) -> dict[str, Any]:
    """Fetch public OHLCV and run CIN's existing deterministic technical analysis."""
    normalized = _validate(symbol, interval, limit)
    rows = await _load(normalized, interval, limit)
    try:
        analysis = analyze_ohlc([{key: row[key] for key in ("open", "high", "low", "close")} for row in rows])
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=f"Fetched candles failed analysis validation: {exc}") from exc
    analysis["input"].update({
        "symbol": normalized,
        "timeframe": interval,
        "source": "Binance public market-data API",
        "source_endpoint": BINANCE_KLINES_URL,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "first_candle_open_time_utc": datetime.fromtimestamp(rows[0]["open_time"] / 1000, timezone.utc).isoformat(),
        "last_candle_close_time_utc": datetime.fromtimestamp(rows[-1]["close_time"] / 1000, timezone.utc).isoformat(),
        "volume_included_in_source_but_not_used_in_indicators": True,
    })
    analysis["limitations"].extend([
        "Public exchange data is not independently audited by CIN.",
        "The last candle may still be forming; confirm closed-candle status before comparing snapshots.",
        "Technical outputs and ATR scenarios are descriptive research, not investment advice or trade instructions.",
    ])
    return analysis
