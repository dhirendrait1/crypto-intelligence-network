"""Disabled-by-default live chart-evidence preview; not a ranked shortlist."""
from __future__ import annotations

import asyncio
import copy
import os
import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException

try:
    from app.cin_public_market_candles_api import get_market_candles
    from app.cin_shortlist_chart_evidence import chart_evidence
    from app.market_data_step1 import get_public_market_data
    from app.cin_shortlist_market_evidence import coinbase_market_evidence
except ModuleNotFoundError as exc:
    if exc.name not in {"app", "app.cin_public_market_candles_api", "app.cin_shortlist_chart_evidence", "app.market_data_step1", "app.cin_shortlist_market_evidence"}:
        raise
    from cin_public_market_candles_api import get_market_candles
    from cin_shortlist_chart_evidence import chart_evidence
    from market_data_step1 import get_public_market_data
    from cin_shortlist_market_evidence import coinbase_market_evidence

router = APIRouter(tags=["experimental-shortlist-preview"])
_BASES = {"bitcoin": "BTC", "ethereum": "ETH"}
_WINDOWS = {"1h": ("5m", 12), "6h": ("15m", 24), "12h": ("30m", 24),
            "24h": ("1h", 24), "7d": ("4h", 42)}
_MAX_CHART_AGE = {"1h": timedelta(minutes=5), "6h": timedelta(minutes=15),
                  "12h": timedelta(minutes=30), "24h": timedelta(hours=1),
                  "7d": timedelta(hours=4)}
_CACHE_SECONDS = 300
_cache = {}
_failures = {}
_lock = asyncio.Lock()


def _chart_is_fresh(response: dict, horizon: str, now: datetime) -> bool:
    try:
        end = datetime.fromisoformat(response["chart"]["window_end"].replace("Z", "+00:00"))
        if end.tzinfo is None:
            return False
        age = now - end.astimezone(timezone.utc)
        return timedelta(0) <= age <= _MAX_CHART_AGE[horizon]
    except (KeyError, TypeError, AttributeError, ValueError, OverflowError):
        return False


@router.get("/research/shortlist-chart-preview/{asset_id}")
async def shortlist_chart_preview(asset_id: str, horizon: str = "24h", quote: str = "USDT"):
    """Validate a live candle window; other mandatory evidence is not assessed."""
    if os.getenv("CIN_SHORTLIST_PREVIEW_ENABLED") != "1":
        raise HTTPException(status_code=404, detail="Not found")
    if asset_id not in _BASES or horizon not in _WINDOWS or quote not in {"USD", "USDT"}:
        raise HTTPException(status_code=400, detail="Unsupported asset or horizon")
    market_id = _BASES[asset_id] + quote
    key = (asset_id, horizon, quote)
    async with _lock:
        tick = time.monotonic()
        cached = _cache.get(key)
        if (cached and 0 <= tick - cached[0] < _CACHE_SECONDS
                and _chart_is_fresh(cached[1], horizon, datetime.now(timezone.utc))):
            response = copy.deepcopy(cached[1])
            market = response.get("market")
            if market:
                try:
                    observed = datetime.fromisoformat(market["observed_at"].replace("Z", "+00:00"))
                    if observed.tzinfo is None:
                        raise ValueError("naive market time")
                    age = datetime.now(timezone.utc) - observed
                    if age < timedelta(0) or age > timedelta(minutes=15):
                        raise ValueError("stale market")
                except (KeyError, AttributeError, TypeError, ValueError, OverflowError):
                    response["market"] = None
                    if "market" not in response["missing_required_evidence"]:
                        response["missing_required_evidence"].insert(0, "market")
            response["cache_age_seconds"] = round(tick - cached[0], 2)
            return response
        failed_at = _failures.get(key)
        if failed_at is not None and 0 <= tick - failed_at < 60:
            raise HTTPException(status_code=503, detail="Chart evidence temporarily unavailable")
        interval, count = _WINDOWS[horizon]
        try:
            payload = await asyncio.wait_for(
                get_market_candles(symbol=market_id, interval=interval, limit=count + 2),
                timeout=20,
            )
            evidence = chart_evidence(payload, asset_id=asset_id, market_id=market_id,
                                      horizon=horizon, now=datetime.now(timezone.utc))
        except Exception as exc:
            _failures[key] = time.monotonic()
            # A failed or incomplete provider response never becomes eligible.
            raise HTTPException(status_code=503, detail="Chart evidence unavailable or incomplete") from exc
        # Coinbase's ticker is USD only; never relabel it as USDT.
        market = None
        if quote == "USD":
            try:
                market_payload = await asyncio.wait_for(
                    get_public_market_data(coins=asset_id, vs_currency="usd"), timeout=30
                )
                market = coinbase_market_evidence(
                    market_payload, asset_id=asset_id, market_id=market_id,
                    now=datetime.now(timezone.utc),
                )
            except Exception:
                # A failed ticker does not invalidate a separately validated chart.
                market = None
        missing = ["news", "social", "market_sentiment"]
        if market is None:
            missing.insert(0, "market")
        response = {
            "service": "cin", "mode": "read_only", "asset_id": asset_id, "horizon": horizon,
            "chart": evidence, "market": market, "shortlist_status": "not_eligible",
            "missing_required_evidence": missing,
            "scenario": "not_assessed", "probability": None,
            "limitations": [
                "Chart and ticker may come from different exchanges and are not an atomic snapshot.",
                "Chart source authenticity and cross-provider identity have not been independently established.",
                "This is not a ranked shortlist, forecast or investment recommendation.",
            ],
            "cache_age_seconds": 0,
        }
        _failures.pop(key, None)
        _cache[key] = (time.monotonic(), copy.deepcopy(response))
        return response


