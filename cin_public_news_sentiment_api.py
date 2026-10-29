"""Read-only public news search with explicitly heuristic headline sentiment."""
from __future__ import annotations

import asyncio
import json
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(tags=["public-news-sentiment"])
_GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
_RSS_FEEDS = (
    ("CoinDesk public RSS", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
    ("Cointelegraph public RSS", "https://cointelegraph.com/rss"),
)
_USER_AGENT = "CIN-Research-API/0.4.0"
_MAX_PROVIDER_RESPONSE_BYTES = 2_000_000
_MAX_ARTICLE_TITLE_LENGTH = 1_000
_MAX_ARTICLE_URL_LENGTH = 2_048
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
        raw = response.read(_MAX_PROVIDER_RESPONSE_BYTES + 1)
    if len(raw) > _MAX_PROVIDER_RESPONSE_BYTES:
        raise ValueError("GDELT response exceeded the configured size limit")
    return json.loads(raw.decode("utf-8"))



def _rss_query_terms(query: str) -> set[str]:
    """Build a small, explicit relevance filter for RSS fallback headlines."""
    terms = {term.lower() for term in re.findall(r"[a-zA-Z0-9]+", query) if len(term) > 2}
    if terms <= {"cryptocurrency", "cryptocurrencies", "crypto", "news"}:
        return {"crypto", "cryptocurrency", "bitcoin", "ethereum", "blockchain", "token", "defi", "web3", "digital asset"}
    return terms


def _get_rss_articles(query: str, max_records: int) -> tuple[list[dict[str, Any]], str]:
    """Use public crypto-news RSS feeds only when GDELT cannot be reached."""
    terms = _rss_query_terms(query)
    rows: list[dict[str, Any]] = []
    providers: list[str] = []
    for provider, url in _RSS_FEEDS:
        request = urllib.request.Request(
            url,
            headers={"accept": "application/rss+xml, application/xml, text/xml", "user-agent": _USER_AGENT},
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=8) as response:
                raw = response.read(_MAX_PROVIDER_RESPONSE_BYTES + 1)
            if len(raw) > _MAX_PROVIDER_RESPONSE_BYTES:
                raise ValueError("RSS response exceeded the configured size limit")
            root = ET.fromstring(raw)
            providers.append(provider)
            for item in root.iter():
                if item.tag.rsplit("}", 1)[-1].lower() not in {"item", "entry"}:
                    continue
                fields = {}
                for child in list(item):
                    fields[child.tag.rsplit("}", 1)[-1].lower()] = (child.text or "").strip()
                title = fields.get("title", "")
                link = fields.get("link", "")
                if not link:
                    link_element = next((child for child in list(item) if child.tag.rsplit("}", 1)[-1].lower() == "link"), None)
                    if link_element is not None:
                        link = link_element.attrib.get("href", "")
                searchable = f"{title} {fields.get('description', '')} {fields.get('summary', '')}".lower()
                if title and link and any(term in searchable for term in terms):
                    date_raw = fields.get("pubdate") or fields.get("published") or fields.get("updated")
                    seen_at = None
                    if date_raw:
                        try:
                            parsed_date = parsedate_to_datetime(date_raw)
                            if parsed_date.tzinfo is not None:
                                seen_at = parsed_date.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                            else:
                                seen_at = parsed_date.replace(tzinfo=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                        except (TypeError, ValueError, OverflowError):
                            seen_at = None
                    rows.append({"title": title, "url": link, "seendate": seen_at, "domain": urlsplit(link).hostname})
                    if len(rows) >= max_records:
                        break
            if len(rows) >= max_records:
                break
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ET.ParseError, ValueError):
            continue
    if not providers:
        raise urllib.error.URLError("GDELT and public RSS fallback feeds were unreachable")
    parsed = _parse_articles({"articles": rows}, max_records)
    return parsed, " + ".join(providers) + " (public RSS fallback; query-filtered)"


def _headline_sentiment(title: str, language: str | None = None) -> dict[str, Any]:
    """Score English headlines only; never label a known non-English headline neutral."""
    normalized_language = language.strip().lower().replace("_", "-").split("-", 1)[0] if isinstance(language, str) and language.strip() else None
    if normalized_language is not None and normalized_language != "en":
        return {
            "label": "unavailable",
            "score": None,
            "positive_terms_matched": 0,
            "negative_terms_matched": 0,
            "confidence": "unsupported_language",
            "language_status": "unsupported_language",
            "method": "English-only keyword lexicon; sentiment not scored for this provider-declared language",
        }
    words = {word.strip(".,:;!?()[]{}\"'").lower() for word in title.split()}
    positive = len(words & _POSITIVE)
    negative = len(words & _NEGATIVE)
    matched = positive + negative
    score = (positive - negative) / matched if matched else 0.0
    label = "positive" if score > 0 else ("negative" if score < 0 else "neutral")
    confidence = "low" if matched <= 1 else "low_to_moderate"
    language_status = "supported_english" if normalized_language == "en" else "language_unverified"
    return {
        "label": label,
        "score": round(score, 4),
        "positive_terms_matched": positive,
        "negative_terms_matched": negative,
        "confidence": confidence,
        "language_status": language_status,
        "method": "Small transparent English headline keyword lexicon; not a trained financial sentiment model",
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


def _normalize_provider_timestamp(value: Any, now: datetime | None = None) -> tuple[str | None, str]:
    """Validate GDELT's seen time; it is not necessarily the article's publication time."""
    if value is None:
        return None, "missing"
    if not isinstance(value, str):
        return None, "invalid"
    if not value.strip():
        return None, "missing"
    raw = value.strip()
    try:
        if len(raw) == 16 and raw.endswith("Z") and "T" in raw:
            parsed = datetime.strptime(raw, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        else:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if parsed.tzinfo is None or parsed.utcoffset() is None:
                return None, "invalid_timezone"
        parsed_utc = parsed.astimezone(timezone.utc)
        reference = now or datetime.now(timezone.utc)
        if reference.tzinfo is None or reference.utcoffset() is None:
            raise ValueError("Reference time must be timezone-aware")
        if (parsed_utc - reference.astimezone(timezone.utc)).total_seconds() > 60:
            return parsed_utc.isoformat().replace("+00:00", "Z"), "future_dated"
        return parsed_utc.isoformat().replace("+00:00", "Z"), "valid"
    except (TypeError, ValueError, OverflowError):
        return None, "invalid"


def _article_url_identity(value: str) -> str:
    """Canonicalize URL components used for duplicate detection, not display."""
    parsed = urlsplit(value)
    scheme = parsed.scheme.lower()
    hostname = (parsed.hostname or "").lower()
    if ":" in hostname and not hostname.startswith("["):
        hostname = f"[{hostname}]"
    port = parsed.port
    if port is not None and not (
        (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    ):
        hostname = f"{hostname}:{port}"
    path = parsed.path.rstrip("/") or "/"
    return urllib.parse.urlunsplit((scheme, hostname, path, parsed.query, ""))


def _optional_provider_text(value: Any, max_length: int = 256) -> str | None:
    """Expose optional provider metadata only when it is a bounded string."""
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not normalized or len(normalized) > max_length or any(ord(char) < 32 or ord(char) == 127 for char in normalized):
        return None
    return normalized


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
        if (
            not isinstance(title, str)
            or not title.strip()
            or len(title) > _MAX_ARTICLE_TITLE_LENGTH
            or any(ord(char) < 32 or ord(char) == 127 for char in title)
            or not _is_http_url(url)
            or len(url) > _MAX_ARTICLE_URL_LENGTH
        ):
            continue
        identity = _article_url_identity(url)
        if identity in seen:
            continue
        seen.add(identity)
        raw_provider_timestamp = row.get("seendate")
        normalized_timestamp, timestamp_status = _normalize_provider_timestamp(raw_provider_timestamp)
        # Preserve short raw strings for auditability, but never echo arbitrary
        # nested provider values or unbounded timestamp strings into the API response.
        provider_timestamp = (
            raw_provider_timestamp
            if isinstance(raw_provider_timestamp, str)
            and len(raw_provider_timestamp) <= 64
            and not any(ord(char) < 32 or ord(char) == 127 for char in raw_provider_timestamp)
            else None
        )
        articles.append({
            "title": title.strip(),
            "url": url,
            "provider_seen_at": provider_timestamp,
            "provider_seen_at_utc": normalized_timestamp,
            "provider_seen_at_validation_status": timestamp_status,
            # Backward-compatible aliases; GDELT seendate is not a verified publication timestamp.
            "published_at": provider_timestamp,
            "published_at_utc": normalized_timestamp,
            "published_at_validation_status": timestamp_status,
            "domain": _optional_provider_text(row.get("domain"), 253),
            "language": _optional_provider_text(row.get("language"), 32),
            "source_country": _optional_provider_text(row.get("sourcecountry"), 64),
            "headline_sentiment": _headline_sentiment(title, _optional_provider_text(row.get("language"), 32)),
        })
        if len(articles) >= max_records:
            break
    return articles


def _search(query: str, max_records: int) -> dict[str, Any]:
    try:
        payload = _get_json(query, max_records)
        articles = _parse_articles(payload, max_records)
        source = "GDELT DOC 2.0 public article search"
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
        # GDELT has failed at the network/provider layer; use a bounded,
        # query-filtered RSS fallback rather than returning a fabricated score.
        articles, source = _get_rss_articles(query, max_records)
    labels = [row["headline_sentiment"]["label"] for row in articles]
    counts = {label: labels.count(label) for label in ("positive", "neutral", "negative")}
    total = len(labels)
    score = round((counts["positive"] - counts["negative"]) / total, 4) if total else None
    timestamp_statuses = [row["provider_seen_at_validation_status"] for row in articles]
    timestamp_quality_counts = {
        status: timestamp_statuses.count(status)
        for status in ("valid", "missing", "invalid_timezone", "invalid", "future_dated")
    }
    return {
        "service": "cin",
        "endpoint": "/news-sentiment",
        "mode": "read_only",
        "source": source,
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
            "provider_article_time_preserved_as": "provider_seen_at",
            "legacy_timestamp_aliases": {
                "published_at": "Retained for compatibility; mirrors GDELT seendate and must not be interpreted as a verified publication timestamp."
            },
            "future_dated_provider_timestamps_are_flagged": True,
            "provider_timestamp_quality_counts": timestamp_quality_counts,
            "sentiment_aggregate_includes_all_accepted_headlines_regardless_of_timestamp_status": True,
            "limitations": [
                "Provider timestamp quality counts describe provider indexing/publication metadata, not independently verified original publication times.",
                "GDELT is primary; public RSS feeds are used only when GDELT fails. RSS fallback applies a headline/summary keyword relevance filter.",
                "Public news search coverage and timestamps depend on provider indexing and feed metadata.",
                "Headline sentiment uses an English-only keyword lexicon and can miss context, negation, sarcasm, and asset-specific meaning. Provider-declared non-English headlines are not scored; missing language metadata is marked unverified and must not be assumed English.",
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
            "message": "GDELT or public RSS fallback provider returned an HTTP error.",
            "provider": "GDELT DOC 2.0 and public RSS fallback",
            "error": "http_error",
            "http_status": exc.code,
        }) from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise HTTPException(status_code=503, detail={
            "message": "GDELT and public RSS fallback providers could not be reached.",
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
