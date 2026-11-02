"""Read-only, limited Mastodon public hashtag observation; not a sentiment model."""
from __future__ import annotations

import json
import re
from html.parser import HTMLParser
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any

BASE = "https://mastodon.social"
TAGS = {"bitcoin": "bitcoin", "ethereum": "ethereum"}
MAX_BYTES = 256_000
MAX_POSTS = 20


_POSITIVE = {"bullish", "optimistic", "rally", "growth", "adoption"}
_NEGATIVE = {"bearish", "pessimistic", "crash", "fraud", "hack"}
_NEGATION = {"not", "no", "never", "neither", "without"}


class _PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.blocked = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.blocked += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style"} and self.blocked:
            self.blocked -= 1

    def handle_data(self, data):
        if not self.blocked:
            self.parts.append(data)


def _post_signal(post: dict[str, Any]) -> str:
    """Conservative English keyword hint; no text is returned or persisted."""
    content = post.get("content")
    if post.get("language") != "en" or not isinstance(content, str) or len(content) > 8_000:
        return "unclassified"
    parser = _PlainText()
    parser.feed(content)
    words = set(re.findall(r"[a-z]+", " ".join(parser.parts).lower()))
    if words & _NEGATION:
        return "unclassified"
    positive, negative = bool(words & _POSITIVE), bool(words & _NEGATIVE)
    if positive and negative:
        return "mixed"
    if positive:
        return "positive"
    if negative:
        return "negative"
    return "unclassified"


def fetch_public_observations(asset_id: str, now: datetime | None = None) -> dict[str, Any]:
    """Count recent public hashtag posts from one instance without saving content."""
    tag = TAGS.get(asset_id)
    if tag is None:
        raise ValueError("Unsupported asset")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("A timezone-aware clock is required")
    current = current.astimezone(timezone.utc)
    url = f"{BASE}/api/v1/timelines/tag/{tag}?limit={MAX_POSTS}"
    request = urllib.request.Request(url, headers={
        "Accept": "application/json", "User-Agent": "CIN-Research/1.0"
    }, method="GET")
    with urllib.request.urlopen(request, timeout=8) as response:
        body = response.read(MAX_BYTES + 1)
    if len(body) > MAX_BYTES:
        raise ValueError("Social provider response exceeds the size limit")
    payload = json.loads(body.decode("utf-8"))
    if not isinstance(payload, list) or len(payload) > MAX_POSTS:
        raise ValueError("Invalid social provider response")
    seen, timestamps = set(), []
    signals = {"positive": 0, "negative": 0, "mixed": 0, "unclassified": 0}
    for post in payload:
        if not isinstance(post, dict) or post.get("visibility") != "public":
            continue
        post_id, tags, stamp = post.get("id"), post.get("tags"), post.get("created_at")
        if not isinstance(post_id, str) or not post_id or len(post_id) > 128 or post_id in seen:
            continue
        if not isinstance(tags, list) or not any(
            isinstance(entry, dict) and isinstance(entry.get("name"), str)
            and entry["name"].casefold() == tag for entry in tags
        ):
            continue
        if not isinstance(stamp, str) or len(stamp) > 64:
            continue
        try:
            observed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            if observed.tzinfo is None:
                continue
            observed = observed.astimezone(timezone.utc)
        except (ValueError, OverflowError):
            continue
        if observed > current or current - observed > timedelta(hours=48):
            continue
        seen.add(post_id)
        timestamps.append(observed)
        signals[_post_signal(post)] += 1
    classified = signals["positive"] + signals["negative"] + signals["mixed"]
    if not classified:
        label = "unavailable"
    elif signals["mixed"] or signals["positive"] == signals["negative"]:
        label = "mixed"
    else:
        label = "positive" if signals["positive"] > signals["negative"] else "negative"
    return {
        "asset_id": asset_id, "source": "Mastodon public hashtag timeline",
        "source_url": url, "retrieved_at": current.isoformat(),
        "observation_window_hours": 48, "sample_limit": MAX_POSTS,
        "recent_public_post_count": len(timestamps),
        "newest_post_at": max(timestamps).isoformat() if timestamps else None,
        "status": "observations_available" if timestamps else "no_recent_observations",
        "sentiment": {"label": label, "confidence": "low" if classified else "unavailable",
                      "method": "English keyword hints; not a trained sentiment model",
                      "counts": signals, "classified_posts": classified},
        "limitations": [
            "One instance and one hashtag only; not representative of all crypto social activity.",
            "Posts and hashtags do not establish asset identity or authenticity.",
            "Keyword hints are not a prediction and may miss sarcasm, context, spam or non-English posts.",
            "Public access, moderation rules, availability and usage terms vary by instance.",
        ],
    }

