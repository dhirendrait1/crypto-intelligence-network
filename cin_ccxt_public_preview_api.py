"""Disabled-by-default, public-only CCXT research preview."""
from __future__ import annotations

import asyncio
import os
import threading
from typing import Any
from fastapi import APIRouter, HTTPException, Query

try:
    from app.cin_ccxt_public_adapter import PublicSpotAdapter, PublicDataUnavailable
except ModuleNotFoundError as exc:
    if exc.name not in {"app", "app.cin_ccxt_public_adapter"}:
        raise
    from cin_ccxt_public_adapter import PublicSpotAdapter, PublicDataUnavailable

router = APIRouter(tags=["experimental-ccxt-public-preview"])
_adapter: PublicSpotAdapter | None = None
_adapter_lock = threading.Lock()
_gate = asyncio.Semaphore(1)


def _get_adapter() -> PublicSpotAdapter:
    global _adapter
    with _adapter_lock:
        if _adapter is None:
            _adapter = PublicSpotAdapter()
        return _adapter


async def _execute(kind: str, symbol: str, *, interval: str = "1h", limit: int = 24) -> dict[str, Any]:
    if os.getenv("CIN_CCXT_PREVIEW_ENABLED") != "1":
        raise HTTPException(status_code=404, detail="Not found")
    if symbol not in {"BTC/USD", "ETH/USD", "BTC/USDT", "ETH/USDT"}:
        raise HTTPException(status_code=400, detail="Unsupported spot market")
    try:
        await asyncio.wait_for(_gate.acquire(), timeout=0.25)
    except TimeoutError as exc:
        raise HTTPException(status_code=503, detail="Public market preview is busy") from exc
    try:
        adapter = _get_adapter()
        if kind == "ticker":
            result = await asyncio.wait_for(asyncio.to_thread(adapter.ticker, symbol), timeout=45)
        else:
            result = await asyncio.wait_for(asyncio.to_thread(adapter.candles, symbol, interval, limit), timeout=45)
        return {"service": "cin", "mode": "read_only", "status": "experimental", **result}
    except PublicDataUnavailable as exc:
        raise HTTPException(status_code=503, detail={"message":"Public market data unavailable", "attempts":exc.attempts}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Unsupported request") from exc
    except TimeoutError as exc:
        raise HTTPException(status_code=503, detail="Public market preview timed out") from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Public market preview unavailable") from exc
    finally:
        _gate.release()


@router.get("/research/ccxt/ticker")
async def ticker(symbol: str = "BTC/USD"):
    return await _execute("ticker", symbol)


@router.get("/research/ccxt/candles")
async def candles(symbol: str = "BTC/USD", interval: str = "1h", limit: int = Query(default=24, ge=2, le=200)):
    if os.getenv("CIN_CCXT_PREVIEW_ENABLED") != "1":
        raise HTTPException(status_code=404, detail="Not found")
    if interval not in {"5m", "15m", "1h", "4h", "1d"}:
        raise HTTPException(status_code=400, detail="Unsupported candle interval")
    return await _execute("candles", symbol, interval=interval, limit=limit)
