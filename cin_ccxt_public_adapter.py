"""Experimental public-only CCXT spot adapter; not a trading API or release gate.

The caller receives normalized values only, never the underlying exchange object.
The adapter is not wired into CIN's API until separately staged and validated.
"""
from __future__ import annotations

import math
import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable

_ALLOWED_PROVIDERS = ("kraken", "coinbase")
_ALLOWED_MARKETS = {"BTC/USD", "ETH/USD", "BTC/USDT", "ETH/USDT"}
_INTERVALS_MS = {"5m": 300_000, "15m": 900_000, "1h": 3_600_000, "4h": 14_400_000, "1d": 86_400_000}
_MAX_ROWS = 200


class PublicDataUnavailable(Exception):
    """All eligible providers failed; sanitized attempt details are available."""

    def __init__(self, attempts: list[dict[str, str]]):
        super().__init__("Public market data is unavailable")
        self.attempts = attempts


def _number(value: Any, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Invalid numeric value")
    result = float(value)
    if not math.isfinite(result) or (positive and result <= 0):
        raise ValueError("Invalid numeric value")
    return result


def _timestamp(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("Invalid timestamp")
    return value


def _error_category(exc: Exception) -> str:
    name = type(exc).__name__
    if name in {"RateLimitExceeded", "DDoSProtection"}:
        return "rate_limited"
    if name in {"RequestTimeout", "TimeoutError"}:
        return "timeout"
    if name in {"NetworkError", "ExchangeNotAvailable", "OnMaintenance"}:
        return "provider_unavailable"
    if name in {"BadSymbol", "NotSupported"}:
        return "unsupported_market"
    return "invalid_or_unavailable"


class PublicSpotAdapter:
    """Small allowlisted facade. No credentials, account methods, or order methods.

    Instances and rate limiters are reused. The local budget is per adapter
    instance/process and counts facade operations, not every CCXT HTTP request.
    A deployment with multiple workers needs an additional shared budget.
    """

    def __init__(self, *, factories: dict[str, Callable] | None = None,
                 clock_ms: Callable[[], int] | None = None,
                 monotonic: Callable[[], float] | None = None):
        if factories is None:
            try:
                import ccxt
            except ImportError as exc:
                raise RuntimeError("Optional CCXT dependency is not installed") from exc
            factories = {"kraken": ccxt.kraken, "coinbase": ccxt.coinbase}
        if not isinstance(factories, dict) or any(k not in _ALLOWED_PROVIDERS for k in factories):
            raise ValueError("Unsupported provider factory")
        self.__clock_ms = clock_ms or (lambda: int(time.time() * 1000))
        self.__monotonic = monotonic or time.monotonic
        self.__providers = {}
        self.__locks = {}
        self.__budgets = {}
        for name in _ALLOWED_PROVIDERS:
            if name in factories:
                # Public-only construction: no API key, secret, wallet or account.
                self.__providers[name] = factories[name]({"enableRateLimit": True, "timeout": 10000})
                self.__locks[name] = threading.Lock()
                self.__budgets[name] = []

    def __market(self, exchange: Any, symbol: str) -> dict:
        markets = exchange.load_markets()
        if not isinstance(markets, dict):
            raise ValueError("Market metadata unavailable")
        market = markets.get(symbol)
        base, quote = symbol.split("/")
        if (not isinstance(market, dict) or market.get("symbol") != symbol
                or market.get("base") != base or market.get("quote") != quote
                or not isinstance(market.get("id"), str) or not market["id"].strip()
                or len(market["id"]) > 128
                or market.get("spot") is not True or market.get("active") is not True):
            raise ValueError("Market identity or status is not verified")
        return market

    def __call(self, symbol: str, operation: str, providers: tuple[str, ...], **kwargs: Any) -> dict:
        if symbol not in _ALLOWED_MARKETS:
            raise ValueError("Unsupported spot market")
        if not isinstance(providers, tuple) or not providers or len(set(providers)) != len(providers) or any(p not in _ALLOWED_PROVIDERS for p in providers):
            raise ValueError("Unsupported provider selection")
        attempts = []
        for provider in providers:
            exchange = self.__providers.get(provider)
            if exchange is None:
                attempts.append({"provider": provider, "reason": "not_configured"})
                continue
            with self.__locks[provider]:
                tick = self.__monotonic()
                recent = [t for t in self.__budgets[provider] if 0 <= tick - t < 60]
                self.__budgets[provider] = recent
                if len(recent) >= 20:
                    attempts.append({"provider": provider, "reason": "local_budget_exhausted"})
                    continue
                recent.append(tick)
                try:
                    market = self.__market(exchange, symbol)
                    now = _timestamp(self.__clock_ms())
                    if operation == "ticker":
                        raw = exchange.fetch_ticker(symbol)
                        result = self.__ticker(raw, symbol, now)
                    elif operation == "candles":
                        raw = exchange.fetch_ohlcv(symbol, timeframe=kwargs["interval"], limit=kwargs["limit"] + 1)
                        result = self.__candles(raw, now, kwargs["interval"], kwargs["limit"])
                    else:
                        raise ValueError("Unsupported public operation")
                    return {"provider": provider, "market_id": market.get("id"), "symbol": symbol,
                            "market_type": "spot", "quote_currency": symbol.split("/")[1],
                            "retrieved_at": datetime.fromtimestamp(now / 1000, tz=timezone.utc).isoformat(),
                            "attempts": attempts, **result}
                except Exception as exc:
                    attempts.append({"provider": provider, "reason": _error_category(exc)})
        raise PublicDataUnavailable(attempts)

    @staticmethod
    def __ticker(raw: Any, symbol: str, now: int) -> dict:
        if not isinstance(raw, dict) or raw.get("symbol") != symbol:
            raise ValueError("Ticker market mismatch")
        price = _number(raw.get("last"), positive=True)
        observed = _timestamp(raw.get("timestamp"))
        if observed > now or now - observed > 900_000:
            raise ValueError("Ticker timestamp unavailable, future or stale")
        return {"kind": "ticker", "last": price, "observed_at_ms": observed,
                "limitations": ["Provider timestamp and identity are not independently verified."]}

    @staticmethod
    def __candles(raw: Any, now: int, interval: str, limit: int) -> dict:
        duration = _INTERVALS_MS[interval]
        if not isinstance(raw, list) or len(raw) > limit + 1:
            raise ValueError("Invalid candle response")
        rows = []
        for row in raw:
            if not isinstance(row, (list, tuple)) or len(row) != 6:
                raise ValueError("Invalid candle")
            ts = _timestamp(row[0])
            op, high, low, close = (_number(x, positive=True) for x in row[1:5])
            volume = _number(row[5])
            if volume < 0 or high < max(op, close) or low > min(op, close) or high < low or ts % duration:
                raise ValueError("Invalid OHLCV or interval alignment")
            if ts + duration <= now:
                rows.append([ts, op, high, low, close, volume])
            elif ts > now:
                raise ValueError("Future candle")
        if len(rows) != limit or any(b[0] - a[0] != duration for a, b in zip(rows, rows[1:])):
            raise ValueError("Incomplete, duplicate or discontinuous candle window")
        if now - (rows[-1][0] + duration) > duration * 2:
            raise ValueError("Stale candle window")
        return {"kind": "ohlcv", "interval": interval, "closed_candles": True,
                "observed_at_ms": rows[-1][0] + duration, "count": len(rows), "data": rows,
                "limitations": ["Provider identity and source authenticity are not independently verified."]}

    def ticker(self, symbol: str, *, providers: tuple[str, ...] = _ALLOWED_PROVIDERS) -> dict:
        return self.__call(symbol, "ticker", providers)

    def candles(self, symbol: str, interval: str, limit: int, *, providers: tuple[str, ...] = _ALLOWED_PROVIDERS) -> dict:
        if interval not in _INTERVALS_MS or type(limit) is not int or not 2 <= limit <= _MAX_ROWS:
            raise ValueError("Unsupported candle interval or limit")
        return self.__call(symbol, "candles", providers, interval=interval, limit=limit)
