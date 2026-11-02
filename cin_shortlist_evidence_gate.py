"""Deterministic evidence gate for research shortlists; no provider calls."""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlsplit

HORIZONS = ("1h", "6h", "12h", "24h", "7d")
CHART_INTERVALS = {
    "1h": timedelta(minutes=5), "6h": timedelta(minutes=15),
    "12h": timedelta(minutes=30), "24h": timedelta(hours=1),
    "7d": timedelta(hours=4),
}
WINDOWS = {
    "1h": timedelta(hours=1), "6h": timedelta(hours=6),
    "12h": timedelta(hours=12), "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
}
REQUIRED = ("market", "chart", "news", "social", "market_sentiment")


def evaluate(candidates: list[dict[str, Any]], horizon: str, now: datetime) -> dict[str, Any]:
    """Gate caller-supplied evidence. Source authenticity must be verified upstream."""
    if horizon not in HORIZONS or not isinstance(now, datetime) or now.tzinfo is None:
        raise ValueError("unsupported horizon or naive clock")
    if not isinstance(candidates, list) or len(candidates) > 100:
        raise ValueError("candidates must be a list of at most 100 items")
    now = now.astimezone(timezone.utc)
    max_ages = {"market": timedelta(minutes=15), "chart": CHART_INTERVALS[horizon],
                "news": timedelta(hours=48), "social": timedelta(hours=48),
                "market_sentiment": timedelta(hours=24)}
    accepted, excluded, seen = [], [], set()
    for item in candidates:
        if not isinstance(item, dict):
            excluded.append({"asset_id": None, "reasons": ["invalid candidate"]})
            continue
        reasons = []
        asset = item.get("asset_id")
        market = item.get("market_id")
        if not isinstance(asset, str) or not asset.strip() or not isinstance(market, str) or not market.strip():
            reasons.append("Asset and market identity are required.")
        elif asset.strip().casefold() in seen:
            reasons.append("Duplicate asset.")
        evidence = item.get("evidence")
        if not isinstance(evidence, dict):
            evidence = {}
        for key in REQUIRED:
            entry = evidence.get(key)
            if not isinstance(entry, dict) or entry.get("status") != "available":
                reasons.append(key + ": unavailable")
                continue
            if entry.get("asset_id") != asset:
                reasons.append(key + ": asset mismatch")
            if not isinstance(entry.get("source"), str) or not entry["source"].strip():
                reasons.append(key + ": missing source")
            try:
                url = urlsplit(entry["source_url"])
                if url.scheme != "https" or not url.hostname or url.username or url.password or url.port is not None:
                    raise ValueError("invalid source URL")
            except (KeyError, TypeError, ValueError, AttributeError):
                reasons.append(key + ": invalid source URL")
            try:
                stamp = datetime.fromisoformat(entry["observed_at"].replace("Z", "+00:00"))
                if stamp.tzinfo is None or stamp > now or now - stamp > max_ages[key]:
                    raise ValueError("not fresh")
            except (KeyError, TypeError, ValueError, OverflowError, AttributeError):
                reasons.append(key + ": stale or invalid timestamp")
        chart = evidence.get("chart")
        if not isinstance(chart, dict) or chart.get("horizon") != horizon or chart.get("closed_candles") is not True or chart.get("coverage") != "complete":
            reasons.append("chart: horizon and completed coverage not established")
        if isinstance(chart, dict):
            if chart.get("market_id") != market:
                reasons.append("chart: market mismatch")
            try:
                start = datetime.fromisoformat(chart["window_start"].replace("Z", "+00:00"))
                end = datetime.fromisoformat(chart["window_end"].replace("Z", "+00:00"))
                minimum = WINDOWS[horizon]
                if start.tzinfo is None or end.tzinfo is None or end > now or end - start < minimum or now - end > max_ages["chart"]:
                    raise ValueError("invalid chart window")
            except (KeyError, TypeError, ValueError, OverflowError, AttributeError):
                reasons.append("chart: invalid or incomplete time window")
        market_evidence = evidence.get("market")
        if not isinstance(market_evidence, dict) or market_evidence.get("market_id") != market:
            reasons.append("market: identity mismatch")
        price = market_evidence.get("price") if isinstance(market_evidence, dict) else None
        try:
            valid_price = not isinstance(price, bool) and isinstance(price, (int, float)) and math.isfinite(price) and price > 0
        except OverflowError:
            valid_price = False
        if not valid_price:
            reasons.append("market: valid price unavailable")
        if reasons:
            excluded.append({"asset_id": asset, "reasons": reasons})
        else:
            seen.add(asset.strip().casefold())
            accepted.append({"asset_id": asset, "market_id": market, "price": price,
                             "scenario": "not_assessed", "probability": None,
                             "invalidation": None, "evidence": evidence})
    # No predictive ranking is asserted until the scenario method is validated.
    return {"horizon": horizon, "as_of": now.isoformat(), "eligible": accepted[:5],
            "excluded": excluded, "ranking_status": "not_assessed",
            "limitations": ["Evidence is caller supplied; authenticity must be verified upstream.",
                            "Market identity and chart coverage fields are assertions and require independent provider verification.",
                            "No forecast or probability is produced by this gate."]}

