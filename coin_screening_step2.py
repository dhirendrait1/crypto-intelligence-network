"""CIN Step 2/3: explainable screening with explicit asset-type classification."""
from __future__ import annotations

import asyncio
import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(tags=["coin-screening"])
URL = "https://api.coingecko.com/api/v3/coins/markets"
_CACHE_TTL_SECONDS = 90
_STALE_CACHE_MAX_SECONDS = 900
_CACHE: dict[tuple[str, int], tuple[float, list[dict[str, Any]]]] = {}
_CACHE_LOCK = threading.Lock()

# Conservative symbol/name heuristics only; this is not a canonical token taxonomy.
STABLE_SYMBOLS = {
    "USDT", "USDC", "DAI", "FDUSD", "USDE", "USDS", "TUSD", "USDD",
    "PYUSD", "USDP", "FRAX", "LUSD", "GUSD", "EURC", "EURT", "USTC",
}
WRAPPED_SYMBOLS = {
    "WBTC", "WETH", "WBNB", "WMATIC", "WAVAX", "WFTM", "WSOL",
    "STETH", "WSTETH", "CBETH", "RETH", "WEETH", "EZETH",
}


def _number(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _asset_type(coin: dict[str, Any]) -> tuple[str, str]:
    symbol = str(coin.get("symbol", "")).upper()
    name = str(coin.get("name", "")).lower()
    coin_id = str(coin.get("id", "")).lower()
    if symbol in STABLE_SYMBOLS or any(word in name for word in ("usd coin", "tether", "stablecoin")):
        return "stablecoin", "Symbol/name heuristic; verify peg and issuer independently"
    if symbol in WRAPPED_SYMBOLS or any(word in name for word in ("wrapped ", " liquid staked", "staked ether")):
        return "wrapped_or_staked", "Symbol/name heuristic; wrapper or staking status may require verification"
    if "wrapped" in coin_id or coin_id.startswith("wrapped-"):
        return "wrapped_or_staked", "Coin ID heuristic; verify asset structure independently"
    return "other_crypto", "Default classification; not a verified asset taxonomy"


def _request_markets(vs_currency: str, per_page: int) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode({
        "vs_currency": vs_currency,
        "order": "market_cap_desc",
        "per_page": per_page,
        "page": 1,
        "sparkline": "false",
        "price_change_percentage": "24h",
    })
    req = urllib.request.Request(
        f"{URL}?{params}",
        headers={"accept": "application/json", "user-agent": "CIN-Research-API/0.3.0"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=15) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Unexpected market-data response")
    return [row for row in payload if isinstance(row, dict)]



def _fetch_markets(vs_currency: str, per_page: int) -> tuple[list[dict[str, Any]], str, int]:
    key = (vs_currency, per_page)
    now = time.time()
    with _CACHE_LOCK:
        cached = _CACHE.get(key)
    if cached and now - cached[0] <= _CACHE_TTL_SECONDS:
        return cached[1], "cache", 0
    try:
        rows = _request_markets(vs_currency, per_page)
        with _CACHE_LOCK:
            _CACHE[key] = (time.time(), rows)
        return rows, "live", 0
    except urllib.error.HTTPError as exc:
        if cached and now - cached[0] <= _STALE_CACHE_MAX_SECONDS:
            return cached[1], "stale_cache", exc.code
        raise
    except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError):
        if cached and now - cached[0] <= _STALE_CACHE_MAX_SECONDS:
            return cached[1], "stale_cache", 0
        raise

def _score(coin: dict[str, Any]) -> dict[str, Any]:
    market_cap = _number(coin.get("market_cap"))
    volume = _number(coin.get("total_volume"))
    fdv = _number(coin.get("fully_diluted_valuation"))
    circulating = _number(coin.get("circulating_supply"))
    total_supply = _number(coin.get("total_supply"))
    change = _number(coin.get("price_change_percentage_24h"))
    asset_type, classification_note = _asset_type(coin)
    score = 0
    reasons: list[str] = []
    warnings: list[str] = []

    if market_cap is not None and market_cap >= 100_000_000:
        score += 20
        reasons.append("Market cap at least 100M in selected currency")
    elif market_cap is None:
        warnings.append("Market-cap data missing")
    else:
        warnings.append("Market cap below preliminary 100M threshold")

    if volume is not None and volume >= 5_000_000:
        score += 20
        reasons.append("24h volume at least 5M in selected currency")
    elif volume is None:
        warnings.append("24h volume data missing")
    else:
        warnings.append("24h volume below preliminary 5M threshold")

    if market_cap and volume is not None:
        ratio = volume / market_cap
        if ratio >= 0.01:
            score += 20
            reasons.append("24h volume / market cap is at least 1%")
        else:
            warnings.append("Low 24h volume relative to market cap")
    else:
        ratio = None
        warnings.append("Volume-to-market-cap ratio unavailable")

    if fdv is not None and market_cap is not None and fdv > 0:
        fdv_gap = max(0.0, (fdv - market_cap) / fdv)
        if fdv_gap <= 0.25:
            score += 15
            reasons.append("FDV-to-market-cap gap is at most 25%")
        else:
            warnings.append("Large FDV-to-market-cap gap; inspect dilution risk")
    else:
        fdv_gap = None
        warnings.append("FDV or market-cap data missing; dilution risk not scored")

    if circulating is not None and total_supply is not None and total_supply > 0:
        circulating_ratio = min(1.0, circulating / total_supply)
        if circulating_ratio >= 0.7:
            score += 15
            reasons.append("At least 70% of reported total supply is circulating")
        else:
            warnings.append("Less than 70% of reported total supply is circulating")
    else:
        circulating_ratio = None
        warnings.append("Supply data missing; unlock schedule not verified")

    if change is not None and abs(change) <= 20:
        score += 10
        reasons.append("24h price change within ±20% preliminary volatility band")
    elif change is None:
        warnings.append("24h price-change data missing")
    else:
        warnings.append("Extreme 24h move; review volatility and possible event risk")

    if asset_type == "stablecoin":
        warnings.append("Stablecoin classification is heuristic; peg stability and issuer risk are not assessed")
    elif asset_type == "wrapped_or_staked":
        warnings.append("Wrapped/staked classification is heuristic; depeg, bridge, custody, and staking risks are not assessed")

    return {
        "id": coin.get("id"),
        "symbol": str(coin.get("symbol", "")).upper(),
        "name": coin.get("name"),
        "asset_type": asset_type,
        "asset_type_confidence": "heuristic",
        "asset_type_note": classification_note,
        "price": coin.get("current_price"),
        "market_cap": market_cap,
        "total_volume_24h": volume,
        "volume_to_market_cap": round(ratio, 6) if ratio is not None else None,
        "fully_diluted_valuation": fdv,
        "fdv_gap_ratio": round(fdv_gap, 4) if fdv_gap is not None else None,
        "circulating_supply_ratio": round(circulating_ratio, 4) if circulating_ratio is not None else None,
        "price_change_percentage_24h": change,
        "screen_score": score,
        "max_score": 100,
        "screen_band": "research_candidate" if score >= 70 else ("watchlist" if score >= 45 else "insufficient_fundamental_metrics"),
        "reasons": reasons,
        "warnings": warnings,
        "last_updated": coin.get("last_updated"),
    }


@router.get("/coin-screening")
async def coin_screening(
    vs_currency: str = Query(default="usd", min_length=2, max_length=10, pattern="^[a-zA-Z]+$"),
    per_page: int = Query(default=50, ge=1, le=100),
    min_score: int = Query(default=0, ge=0, le=100),
    asset_type: str = Query(default="all", pattern="^(all|growth|stablecoin|wrapped_or_staked|other_crypto)$"),
):
    """Screen top market-cap assets. Asset-type labels are heuristic. Read-only."""
    currency = vs_currency.lower()
    try:
        raw, data_mode, provider_error_code = await asyncio.to_thread(_fetch_markets, currency, per_page)
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            raise HTTPException(status_code=503, detail="CoinGecko rate limit and no recent cached response; retry later") from exc
        raise HTTPException(status_code=502, detail=f"CoinGecko HTTP error: {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise HTTPException(status_code=503, detail="CoinGecko temporarily unavailable") from exc
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=502, detail="Invalid CoinGecko response") from exc

    results = [_score(coin) for coin in raw]
    if asset_type == "growth":
        results = [coin for coin in results if coin["asset_type"] == "other_crypto"]
    elif asset_type != "all":
        results = [coin for coin in results if coin["asset_type"] == asset_type]
    results = [coin for coin in results if coin["screen_score"] >= min_score]
    results.sort(key=lambda item: (item["screen_score"], item["market_cap"] or 0), reverse=True)
    return {
        "service": "cin",
        "endpoint": "/coin-screening",
        "source": "CoinGecko public API",
        "mode": "read_only",
        "data_mode": data_mode,
        "stale_data_warning": ("CoinGecko is unavailable or rate-limiting; results use cached market data and may be up to 15 minutes old." if data_mode == "stale_cache" else None),
        "provider_error_code": provider_error_code or None,
        "methodology": "Preliminary transparent heuristic; not financial advice or a safety rating",
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "currency": currency.upper(),
        "count": len(results),
        "parameters": {"per_page": per_page, "min_score": min_score, "asset_type": asset_type},
        "score_weights": {
            "market_cap": 20,
            "volume_24h": 20,
            "volume_to_market_cap": 20,
            "fdv_gap": 15,
            "circulating_supply_ratio": 15,
            "24h_change_band": 10,
        },
        "asset_classification": "Heuristic symbol/name/ID classification; validate independently before research decisions",
        "limitations": [
            "Initial screen covers the top market-cap assets returned by CoinGecko, not every token.",
            "A missing value receives no points and generates a warning.",
            "Stablecoin and wrapped/staked labels are heuristics and may misclassify assets.",
            "Token unlock schedules, project utility, developer activity, audits, exploits, holder concentration, and exchange-specific liquidity are not yet verified.",
            "Score is a research prioritization aid, not a prediction, endorsement, or guarantee of safety.",
        ],
        "data": results,
    }
