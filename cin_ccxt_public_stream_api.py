"""Experimental bounded public Kraken trade stream; disabled unless explicitly enabled."""
from __future__ import annotations

import asyncio
import json
import math
import os
import time
from collections import deque
from typing import Any
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

router = APIRouter(tags=["experimental-ccxt-public-stream"])
_ALLOWED = {"BTC/USD", "ETH/USD"}
_MAX_SECONDS = 120
_MAX_EVENTS = 120
_MAX_TRADE_AGE_MS = 30_000
_slot = asyncio.Semaphore(1)
_next_start = 0.0
_COOLDOWN_SECONDS = 30


def _make_exchange():
    # This code path is lazy and receives no API credentials or account details.
    import ccxt.pro as pro
    return pro.kraken({"enableRateLimit": True, "timeout": 10000, "options": {"tradesLimit": 100}})


def _event(kind: str, data: dict[str, Any]) -> str:
    return "event: " + kind + "\ndata: " + json.dumps(data, separators=(",", ":"), allow_nan=False) + "\n\n"


def _trade(raw: Any, symbol: str, now_ms: int) -> dict | None:
    if not isinstance(raw, dict) or raw.get("symbol") != symbol:
        return None
    trade_id = raw.get("id")
    timestamp = raw.get("timestamp")
    price, amount = raw.get("price"), raw.get("amount")
    if not isinstance(trade_id, str) or not trade_id or len(trade_id) > 128:
        return None
    if isinstance(timestamp, bool) or not isinstance(timestamp, int) or timestamp > now_ms or now_ms - timestamp > _MAX_TRADE_AGE_MS:
        return None
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0 for v in (price, amount)):
        return None
    return {"id": trade_id, "observed_at_ms": timestamp, "price": float(price), "quantity": float(amount)}


async def _events(request: Request, symbol: str):
    global _next_start
    exchange = None
    seen: set[str] = set()
    order: deque[str] = deque()
    try:
        exchange = _make_exchange()
        markets = await asyncio.wait_for(exchange.load_markets(), timeout=30)
        market = markets.get(symbol) if isinstance(markets, dict) else None
        base, quote = symbol.split('/')
        if (not isinstance(market, dict) or market.get('symbol') != symbol
                or market.get('base') != base or market.get('quote') != quote
                or market.get('spot') is not True or market.get('active') is not True
                or not isinstance(market.get('id'), str) or not market['id'].strip()
                or len(market['id']) > 128):
            yield _event('unavailable', {'reason':'market_identity_unverified'})
            return
        yield _event('connected', {'provider':'kraken','symbol':symbol,'market_id':market['id'],
                                  'market_type':'spot','mode':'read_only',
                                  'message':'Public stream connected; no trade received yet.'})
        connected_at_ms = int(time.time() * 1000)
        start = time.monotonic()
        emitted = 0
        timeouts = 0
        while time.monotonic() - start < _MAX_SECONDS and emitted < _MAX_EVENTS:
            if await request.is_disconnected():
                return
            remaining = _MAX_SECONDS - (time.monotonic() - start)
            try:
                batch = await asyncio.wait_for(exchange.watch_trades(symbol, limit=20), timeout=min(12, max(.01, remaining)))
            except TimeoutError:
                timeouts += 1
                if timeouts >= 3:
                    yield _event('unavailable', {'reason':'no_recent_updates'})
                    return
                yield ': waiting for public market update\n\n'
                continue
            if not isinstance(batch, list) or len(batch) > 100:
                yield _event('unavailable', {'reason':'invalid_provider_response'})
                return
            timeouts = 0
            now_ms = int(time.time() * 1000)
            accepted = 0
            for raw in batch:
                item = _trade(raw, symbol, now_ms)
                if item is None or item['observed_at_ms'] < connected_at_ms or item['id'] in seen:
                    continue
                seen.add(item['id']); order.append(item['id'])
                if len(order) > 500:
                    seen.discard(order.popleft())
                emitted += 1
                accepted += 1
                yield _event('trade', {'provider':'kraken','symbol':symbol,
                                       'market_id':market['id'],'market_type':'spot',
                                       'price_currency':quote,'quantity_currency':base,
                                       'price':item['price'],'quantity':item['quantity'],
                                       'provider_observed_at_ms':item['observed_at_ms'],
                                       'received_at_ms':now_ms,
                                       'limitations':['Provider identity and timestamp are not independently verified.']})
                if emitted >= _MAX_EVENTS:
                    break
            if not accepted:
                # Protect against an implementation repeatedly returning its cache.
                await asyncio.sleep(0.1)
        yield _event('closed', {'reason':'preview_limit_reached'})
    except asyncio.CancelledError:
        raise
    except Exception:
        yield _event('unavailable', {'reason':'public_stream_unavailable'})
    finally:
        if exchange is not None:
            try:
                await asyncio.wait_for(exchange.close(), timeout=5)
            except Exception:
                pass
        _next_start = time.monotonic() + _COOLDOWN_SECONDS
        _slot.release()


@router.get('/research/ccxt/public-trades-stream')
async def public_trades_stream(request: Request, symbol: str = 'BTC/USD'):
    if os.getenv('CIN_CCXT_PREVIEW_ENABLED') != '1' or os.getenv('CIN_CCXT_STREAM_ENABLED') != '1':
        raise HTTPException(status_code=404, detail='Not found')
    if symbol not in _ALLOWED:
        raise HTTPException(status_code=400, detail='Unsupported spot market')
    if time.monotonic() < _next_start:
        raise HTTPException(status_code=503, detail='Public stream preview is cooling down', headers={'Retry-After':'30'})
    try:
        await asyncio.wait_for(_slot.acquire(), timeout=0.25)
    except TimeoutError as exc:
        raise HTTPException(status_code=503, detail='Public stream preview is busy', headers={'Retry-After':'15'}) from exc
    try:
        return StreamingResponse(_events(request, symbol), media_type='text/event-stream',
                                 headers={'Cache-Control':'no-store', 'X-Accel-Buffering':'no'})
    except BaseException:
        _slot.release()
        raise
