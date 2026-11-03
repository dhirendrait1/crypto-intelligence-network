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
_pending = 0
_MAX_PENDING = 4
_QUEUE_TIMEOUT_SECONDS = 20


def _get_adapter() -> PublicSpotAdapter:
    global _adapter
    with _adapter_lock:
        if _adapter is None:
            _adapter = PublicSpotAdapter()
        return _adapter


async def _execute(kind: str, symbol: str, *, interval: str = "1h", limit: int = 24) -> dict[str, Any]:
    global _pending
    if os.getenv("CIN_CCXT_PREVIEW_ENABLED") != "1":
        raise HTTPException(status_code=404, detail="Not found")
    if symbol not in {"BTC/USD", "ETH/USD", "BTC/USDT", "ETH/USDT"}:
        raise HTTPException(status_code=400, detail="Unsupported spot market")
    # Admission and decrement run on the event loop without an intervening await.
    # This cap is per process; a multi-worker deployment needs shared controls.
    if _pending >= _MAX_PENDING:
        raise HTTPException(status_code=503, detail="Public market preview queue is full", headers={"Retry-After": "5"})
    _pending += 1
    acquired = False
    release_on_completion = False
    try:
        try:
            await asyncio.wait_for(_gate.acquire(), timeout=_QUEUE_TIMEOUT_SECONDS)
            acquired = True
        except TimeoutError as exc:
            raise HTTPException(status_code=503, detail="Public market preview is busy; retry shortly", headers={"Retry-After": "5"}) from exc
        adapter = _get_adapter()
        if kind == "ticker":
            task = asyncio.create_task(asyncio.to_thread(adapter.ticker, symbol))
        elif kind == "candles":
            task = asyncio.create_task(asyncio.to_thread(adapter.candles, symbol, interval, limit))
        elif kind == "order_book":
            task = asyncio.create_task(asyncio.to_thread(adapter.order_book, symbol))
        elif kind == "comparison":
            task = asyncio.create_task(asyncio.to_thread(adapter.compare_closed_candles, symbol))
        else:
            raise ValueError("Unsupported request")
        # A timed-out thread cannot be cancelled. Retain the gate until it
        # actually finishes so another worker cannot overlap it in this process.
        def release_gate(completed: asyncio.Task) -> None:
            _gate.release()
            if not completed.cancelled():
                completed.exception()  # Consume late exceptions after timeout/cancellation.
        task.add_done_callback(release_gate)
        release_on_completion = True
        result = await asyncio.wait_for(asyncio.shield(task), timeout=45)
        return {"service": "cin", "mode": "read_only", "status": "experimental", **result}
    except HTTPException:
        raise
    except PublicDataUnavailable as exc:
        raise HTTPException(status_code=503, detail={"message":"Public market data unavailable", "attempts":exc.attempts}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Unsupported request") from exc
    except TimeoutError as exc:
        raise HTTPException(status_code=503, detail="Public market preview timed out") from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Public market preview unavailable") from exc
    finally:
        if acquired and not release_on_completion:
            _gate.release()
        _pending -= 1


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


@router.get("/research/ccxt/order-book")
async def order_book(symbol: str = "BTC/USD"):
    return await _execute("order_book", symbol)


@router.get("/research/ccxt/closed-candle-comparison")
async def closed_candle_comparison(symbol: str = "BTC/USD"):
    return await _execute("comparison", symbol)


@router.get("/research/ccxt/provider-observations")
async def provider_observations():
    if os.getenv("CIN_CCXT_PREVIEW_ENABLED") != "1":
        raise HTTPException(status_code=404, detail="Not found")
    # Do not initialize CCXT, contact providers or expose configured secrets.
    if _adapter is None:
        return {"service":"cin", "mode":"read_only", "status":"experimental",
                "scope":"current_process_only", "providers":[],
                "limitations":["No adapter activity has been observed in this process."]}
    return {"service":"cin", "mode":"read_only", "status":"experimental", **_adapter.provider_observations()}
