"""Construct preliminary shortlist chart evidence from a CIN candle response.

Provider identity is not independently verified; callers must establish it.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

_RULES = {
    "1h": ("5m", 12, 300_000),
    "6h": ("15m", 24, 900_000),
    "12h": ("30m", 24, 1_800_000),
    "24h": ("1h", 24, 3_600_000),
    "7d": ("4h", 42, 14_400_000),
}


def chart_evidence(payload: Any, *, asset_id: str, market_id: str, horizon: str, now: datetime) -> dict[str, Any]:
    if horizon not in _RULES or not isinstance(now, datetime) or now.tzinfo is None:
        raise ValueError("Invalid horizon or clock")
    if not isinstance(asset_id, str) or not asset_id.strip() or not isinstance(market_id, str) or not market_id.strip():
        raise ValueError("Asset and market IDs are required")
    if not isinstance(payload, dict) or payload.get("symbol") != market_id:
        raise ValueError("Candle market does not match")
    interval, count, duration = _RULES[horizon]
    if payload.get("timeframe") != interval:
        raise ValueError("Candle interval does not match horizon")
    if payload.get("pair_metadata_status") != "identified" or not payload.get("quote_currency"):
        raise ValueError("Market quote identity unavailable")
    if not isinstance(payload.get("source"), str) or not payload["source"].strip():
        raise ValueError("Candle source unavailable")
    endpoint = payload.get("source_endpoint")
    if not isinstance(endpoint, str) or not endpoint.startswith("https://"):
        raise ValueError("Candle source URL unavailable")
    rows = payload.get("data")
    if not isinstance(rows, list) or len(rows) > 500 or payload.get("count") != len(rows):
        raise ValueError("Candle collection invalid")
    # Forming rows may occur only at the end and are excluded from analysis.
    closed = []
    forming_seen = False
    previous_open = None
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Invalid candle")
        start, end = row.get("open_time"), row.get("close_time")
        if type(start) is not int or type(end) is not int or start < 0:
            raise ValueError("Invalid candle timestamp")
        if previous_open is not None and start <= previous_open:
            raise ValueError("Duplicate or unordered candle")
        previous_open = start
        if end not in (start + duration - 1, start + duration):
            raise ValueError("Invalid candle duration")
        for field in ("open", "high", "low", "close"):
            value = row.get(field)
            try:
                valid = not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value) and value > 0
            except OverflowError:
                valid = False
            if not valid:
                raise ValueError("Invalid candle price")
        if row["high"] < max(row["open"], row["close"], row["low"]) or row["low"] > min(row["open"], row["close"]):
            raise ValueError("Invalid candle price relationship")
        now_ms = int(now.timestamp() * 1000)
        computed_closed = end < now_ms
        if type(row.get("is_closed")) is not bool or row["is_closed"] != computed_closed:
            raise ValueError("Candle close status inconsistent")
        if not computed_closed:
            forming_seen = True
        else:
            if forming_seen:
                raise ValueError("Closed candle follows forming candle")
            closed.append(row)
    if len(closed) < count:
        raise ValueError("Insufficient closed candles")
    selected = closed[-count:]
    if any(right["open_time"] - left["open_time"] != duration for left, right in zip(selected, selected[1:])):
        raise ValueError("Candle window contains a gap")
    end_ms = selected[-1]["open_time"] + duration
    if end_ms > int(now.timestamp() * 1000) or int(now.timestamp() * 1000) - end_ms > duration:
        raise ValueError("Latest closed candle is stale")
    def iso(ms: int) -> str:
        try:
            return datetime.fromtimestamp(ms / 1000, timezone.utc).isoformat()
        except (ValueError, OverflowError, OSError) as exc:
            raise ValueError("Unrepresentable candle timestamp") from exc
    return {
        "status": "available", "asset_id": asset_id, "market_id": market_id,
        "source": payload["source"], "source_url": endpoint,
        "observed_at": iso(end_ms), "horizon": horizon,
        "window_start": iso(selected[0]["open_time"]), "window_end": iso(end_ms),
        "closed_candles": True, "coverage": "complete", "candle_count": count,
        "source_authenticity": "not_independently_verified",
        "note": "Continuity reflects returned candles; no-trade gaps are not interpreted as outages.",
    }

