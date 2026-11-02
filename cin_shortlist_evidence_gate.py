"""Deterministic evidence gate for research shortlists; no provider calls."""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any

HORIZONS = ("24h", "7d")
REQUIRED = ("market", "chart", "news", "social", "market_sentiment")


def evaluate(candidates: list[dict[str, Any]], horizon: str, now: datetime) -> dict[str, Any]:
    """Gate caller-supplied evidence. Source authenticity must be verified upstream."""
    if horizon not in HORIZONS or now.tzinfo is None:
        raise ValueError("unsupported horizon or naive clock")
    if not isinstance(candidates, list) or len(candidates) > 100:
        raise ValueError("candidates must be a list of at most 100 items")
    now = now.astimezone(timezone.utc)
    max_ages = {"market": timedelta(minutes=15), "chart": timedelta(hours=4),
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
        elif (asset, market) in seen:
            reasons.append("Duplicate asset and market.")
        else:
            seen.add((asset, market))
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
            if not isinstance(entry.get("source_url"), str) or not entry["source_url"].startswith("https://"):
                reasons.append(key + ": missing source URL")
            try:
                stamp = datetime.fromisoformat(entry["observed_at"].replace("Z", "+00:00"))
                if stamp.tzinfo is None or stamp > now or now - stamp > max_ages[key]:
                    raise ValueError("not fresh")
            except (KeyError, TypeError, ValueError, OverflowError, AttributeError):
                reasons.append(key + ": stale or invalid timestamp")
        chart = evidence.get("chart")
        if not isinstance(chart, dict) or chart.get("horizon") != horizon or chart.get("closed_candles") is not True or chart.get("coverage") != "complete":
            reasons.append("chart: horizon and completed coverage not established")
        market_evidence = evidence.get("market")
        price = market_evidence.get("price") if isinstance(market_evidence, dict) else None
        if isinstance(price, bool) or not isinstance(price, (int, float)) or not math.isfinite(price) or price <= 0:
            reasons.append("market: valid price unavailable")
        if reasons:
            excluded.append({"asset_id": asset, "reasons": reasons})
        else:
            accepted.append({"asset_id": asset, "market_id": market, "price": price,
                             "scenario": "not_assessed", "probability": None,
                             "invalidation": None, "evidence": evidence})
    # No predictive ranking is asserted until the scenario method is validated.
    return {"horizon": horizon, "as_of": now.isoformat(), "eligible": accepted[:5],
            "excluded": excluded, "ranking_status": "not_assessed",
            "limitations": ["Evidence is caller supplied; authenticity must be verified upstream.",
                            "No forecast or probability is produced by this gate."]}

