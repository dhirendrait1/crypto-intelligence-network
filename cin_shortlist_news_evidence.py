"""Conservative mapping of CIN's public news response to shortlist evidence."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlsplit

_ASSETS = {"bitcoin", "ethereum"}


def news_evidence(payload: Any, *, asset_id: str, now: datetime) -> dict[str, Any]:
    """Find a recently indexed article mentioning the full asset name.

    A title match and provider timestamp do not establish article truth,
    original publication time or causal relevance.
    """
    if asset_id not in _ASSETS or not isinstance(now, datetime) or now.tzinfo is None:
        raise ValueError("Unsupported asset or clock")
    if not isinstance(payload, dict) or not isinstance(payload.get("query"), str) or payload["query"].strip().casefold() != asset_id:
        raise ValueError("News query does not match asset")
    source = payload.get("source")
    rows = payload.get("articles")
    if source != "GDELT DOC 2.0 public article search":
        raise ValueError("News source unavailable")
    if not isinstance(rows, list) or len(rows) > 50 or type(payload.get("count")) is not int or payload["count"] != len(rows):
        raise ValueError("Invalid news response")
    current = now.astimezone(timezone.utc)
    matches = []
    for row in rows:
        if not isinstance(row, dict) or row.get("provider_seen_at_validation_status") != "valid":
            continue
        title, link, raw = row.get("title"), row.get("url"), row.get("provider_seen_at_utc")
        if not isinstance(title, str) or len(title) > 512 or any(ord(c) < 32 or ord(c) == 127 for c in title):
            continue
        if re.search(r"(?<![A-Za-z0-9])" + re.escape(asset_id) + r"(?![A-Za-z0-9])", title, re.IGNORECASE) is None:
            continue
        if not isinstance(link, str) or len(link) > 2048 or any(c.isspace() or ord(c) < 32 for c in link) or not isinstance(raw, str) or len(raw) > 64:
            continue
        try:
            url = urlsplit(link)
            if url.scheme != "https" or not url.hostname or url.username or url.password or url.port is not None:
                continue
            stamp = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if stamp.tzinfo is None:
                continue
            stamp = stamp.astimezone(timezone.utc)
        except (ValueError, OverflowError):
            continue
        if stamp > current or current - stamp > timedelta(hours=48):
            continue
        matches.append((stamp, title, link))
    if not matches:
        raise ValueError("No recent matching news")
    stamp, title, link = max(matches, key=lambda item: item[0])
    return {
        "status": "preliminary", "asset_id": asset_id, "source": source,
        "source_url": link, "observed_at": stamp.isoformat(), "headline": title,
        "timestamp_semantics": "provider_seen_at_not_verified_publication_time",
        "limitations": [
            "A title match does not establish article truth or causal relevance.",
            "Provider seen time is not an independently verified publication time.",
            "Headline keyword sentiment is not treated as market sentiment or a forecast.",
        ],
    }

