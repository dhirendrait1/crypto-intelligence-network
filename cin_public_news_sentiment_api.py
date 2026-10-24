"""Read-only public news search with explicitly heuristic headline sentiment."""
from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(tags=["public-news-sentiment"])
_GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
_USER_AGENT = "CIN-Research-API/0.4.0"
_POSITIVE = {
    "adoption", "approved", "approval", "bullish", "gain", "gains", "growth",
    "launch", "launched", "partnership", "positive", "record", "surge", "surges",
    "upgrade", "upgraded", "win", "wins",
}
_NEGATIVE = {
    "ban", "banned", "bearish", "crash", "decline", "declines", "exploit",
    "fraud", "hack", "hacked", "lawsuit", "loss", "losses", "negative",
    "outage", "reject", "rejected", "risk", "risks", "scam", "selloff",
}


def _get_json(query: str, max_records: int) -> Any:
    params = urllib.parse.urlencode({
        "query": query,
        "mode": "ArtList",
        "format": "json",
        "sort": "DateDesc",
        "maxrecords": max_records,
    })
    request = urllib.request.Request(
        f"{_GDELT_URL}?{params}",
        headers={"accept": "application/json", "user-agent": _USER_AGENT},
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=12) as response:
        return json.loads(response.read().decode("utf-8"))


def _headline_sentiment(title: str) -> dict[str, Any]:
    words = {word.strip(".,:;!?()[]{}\"'").lower() for word in title.split()}
    positive = len(words & _POSITIVE)
    negative = len(words & _NEGATIVE)
    matched = positive + negative
    score = (positive - negative) / matched if matched else 0.0
    label = "positive" if score > 0 else ("negative" if score < 0 else "neutral")
    confidence = "low" if matched <= 1 else "low_to_moderate"
    return {
        "label": label,
        "score": round(score, 4),
        "positive_terms_matched": positive,
        "negative_terms_matched": negative,
        "confidence": confidence,
        "method": "Small transparent headline keyword lexicon; not a trained financial sentiment model",
    }


def _is_http_url(value: Any) -> bool:
    """Accept absolute HTTP(S) URLs with a hostname and no embedded credentials."""
    if not isinstance(value, str) or not value or any(
        char.isspace() or ord(char) < 32 or ord(char) == 127 for char in value
    ):
        return False
    try:
        parsed = urlsplit(value)
        # Accessing .port validates that a supplied port is numeric and in range.
        parsed.port
        return (
            parsed.scheme.lower() in {"http", "https"}
            and bool(parsed.hostname)
            and parsed.username is None
            and parsed.password is None
        )
    except ValueError:
        return False


def _parse_articles(payload: Any, max_records: int) -> list[dict[str, Any]]:
    if not isinstance(payload, dict) or not isinstance(payload.get("articles"), list):
        raise ValueError("Unexpected GDELT article-search response")
    articles: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in payload.get("articles", []):
        if not isinstance(row, dict):
            continue
        title = row.get("title")
        url = row.get("url")
        if not isinstance(title, str) or not title.strip() or not _is_http_url(url):
            continue
        if url in seen:
            continue
        seen.add(url)
        articles.append({
            "title": title.strip(),
            "url": url,
            "published_at": row.get("seendate"),
            "domain": row.get("domain"),
            "language": row.get("language"),
            "source_country": row.get("sourcecountry"),
            "headline_sentiment": _headline_sentiment(title),
        })
        if len(articles) >= max_records:
            break
    return articles


def _search(query: str, max_records: int) -> dict[str, Any]:
    payload = _get_json(query, max_records)
    articles = _parse_articles(payload, max_records)
    labels = [row["headline_sentiment"]["label"] for row in articles]
    counts = {label: labels.count(label) for label in ("positive", "neutral", "negative")}
    total = len(labels)
    score = round((counts["positive"] - counts["negative"]) / total, 4) if total else None
    return {
        "service": "cin",
        "endpoint": "/news-sentiment",
        "mode": "read_only",
        "source": "GDELT DOC 2.0 public article search",
        "query": query,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "count": total,
        "sentiment_summary": {
            "label": "positive" if score is not None and score > 0 else ("negative" if score is not None and score < 0 else ("neutral" if score is not None else "unavailable")),
            "score": score,
            "article_label_counts": counts,
            "confidence": "low",
            "warning": "Headline-only keyword sentiment is a coarse research signal; it is not X/social sentiment and does not establish market direction.",
        },
        "articles": articles,
        "data_quality": {
            "deduplicated_by_url": True,
            "provider_article_time_preserved_as": "published_at",
            "limitations": [
                "Public news search coverage and timestamps depend on GDELT indexing.",
                "Headline sentiment uses a small transparent keyword lexicon and can miss context, negation, sarcasm, and asset-specific meaning.",
                "This endpoint does not ingest X, Reddit, Telegram, or other social platforms.",
                "An empty result means no articles were returned for this query, not that news or sentiment is absent globally.",
            ],
        },
    }


@router.get("/news-sentiment")
async def news_sentiment(
    query: str = Query(default="cryptocurrency", min_length=2, max_length=160),
    max_records: int = Query(default=20, ge=1, le=50),
):
    """Search public news and score headlines with a transparent low-confidence lexicon."""
    normalized = " ".join(query.split())
    if len(normalized) < 2:
        raise HTTPException(status_code=422, detail="Query must contain at least two non-whitespace characters.")
    try:
        return await asyncio.to_thread(_search, normalized, max_records)
    except urllib.error.HTTPError as exc:
        status = 503 if exc.code == 429 or exc.code >= 500 else 502
        raise HTTPException(status_code=status, detail={
            "message": "Public news provider returned an HTTP error.",
            "provider": "GDELT DOC 2.0",
            "error": "http_error",
            "http_status": exc.code,
        }) from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise HTTPException(status_code=503, detail={
            "message": "Public news provider could not be reached.",
            "provider": "GDELT DOC 2.0",
            "error": "network_error",
        }) from exc
    except (ValueError, json.JSONDecodeError, RuntimeError, TypeError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=502, detail={
            "message": "Public news provider response was invalid.",
            "provider": "GDELT DOC 2.0",
            "error": "invalid_response",
        }) from exc
    except Exception as exc:
        # Keep unforeseen provider/parser failures inside the controlled API contract.
        raise HTTPException(status_code=502, detail={
            "message": "Public news provider response was invalid.",
            "provider": "GDELT DOC 2.0",
            "error": "invalid_response",
        }) from exc
