"""Translate the experimental social preview to shortlist evidence conservatively."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

_EXPECTED = {
    "bitcoin": "https://mastodon.social/api/v1/timelines/tag/bitcoin?limit=20",
    "ethereum": "https://mastodon.social/api/v1/timelines/tag/ethereum?limit=20",
}
_LABELS = {"positive", "negative", "mixed"}


def social_evidence(payload: Any, *, asset_id: str, now: datetime) -> dict[str, Any]:
    """Validate the preview contract; instance terms and relevance remain unverified."""
    if asset_id not in _EXPECTED or not isinstance(now, datetime) or now.tzinfo is None:
        raise ValueError("Invalid asset or clock")
    if not isinstance(payload, dict) or payload.get("asset_id") != asset_id:
        raise ValueError("Social asset identity mismatch")
    if payload.get("source") != "Mastodon public hashtag timeline" or payload.get("source_url") != _EXPECTED[asset_id]:
        raise ValueError("Unexpected social source")
    if payload.get("status") != "observations_available":
        raise ValueError("No recent social observations")
    n = payload.get("recent_public_post_count")
    sentiment = payload.get("sentiment")
    if type(n) is not int or not 1 <= n <= 20 or not isinstance(sentiment, dict):
        raise ValueError("Invalid social sample")
    label, confidence, counts = sentiment.get("label"), sentiment.get("confidence"), sentiment.get("counts")
    if label not in _LABELS or confidence != "low" or not isinstance(counts, dict):
        raise ValueError("Social sentiment not assessed")
    keys = ("positive", "negative", "mixed", "unclassified")
    if any(type(counts.get(key)) is not int or counts[key] < 0 for key in keys):
        raise ValueError("Invalid social counts")
    classified = sum(counts[key] for key in ("positive", "negative", "mixed"))
    if (sum(counts[key] for key in keys) != n or classified == 0
            or type(sentiment.get("classified_posts")) is not int
            or sentiment["classified_posts"] != classified):
        raise ValueError("Inconsistent social counts")
    computed = ("mixed" if counts["mixed"] or counts["positive"] == counts["negative"]
                else "positive" if counts["positive"] > counts["negative"] else "negative")
    if label != computed:
        raise ValueError("Inconsistent social signal")
    stamp = payload.get("newest_post_at")
    if not isinstance(stamp, str) or len(stamp) > 64:
        raise ValueError("Missing social observation time")
    try:
        observed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        if observed.tzinfo is None:
            raise ValueError("Naive observation time")
        observed = observed.astimezone(timezone.utc)
        current = now.astimezone(timezone.utc)
        if observed > current or current - observed > timedelta(hours=48):
            raise ValueError("Stale or future observation")
    except (ValueError, OverflowError) as exc:
        raise ValueError("Invalid social observation time") from exc
    return {
        "status": "available", "asset_id": asset_id,
        "source": payload["source"], "source_url": payload["source_url"],
        "observed_at": observed.isoformat(), "signal": label, "confidence": "low",
        "sample_count": n, "classified_count": classified,
        "limitations": [
            "Single instance and hashtag, not representative of crypto-wide sentiment.",
            "Hashtag relevance, source rights and user identity are not independently verified.",
            "Keyword-based signal can misread context and is not a prediction.",
        ],
    }

