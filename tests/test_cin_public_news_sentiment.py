"""Offline regression tests for CIN public news search and headline sentiment."""
import asyncio
import urllib.error

import pytest
from fastapi import HTTPException

import cin_public_news_sentiment_api as api


def test_headline_sentiment_is_transparent_and_low_confidence():
    positive = api._headline_sentiment("Bullish adoption gains after approved launch")
    negative = api._headline_sentiment("Exchange hacked after fraud lawsuit")
    neutral = api._headline_sentiment("Bitcoin market update")

    assert positive["label"] == "positive"
    assert positive["confidence"] == "low_to_moderate"
    assert negative["label"] == "negative"
    assert neutral["label"] == "neutral"
    assert "not a trained financial sentiment model" in positive["method"]


def test_parse_articles_deduplicates_and_skips_invalid_urls():
    payload = {
        "articles": [
            {"title": "Bullish adoption", "url": "https://news.example/a", "seendate": "20261024T000000Z", "domain": "news.example"},
            {"title": "Duplicate", "url": "https://news.example/a"},
            {"title": "Unsafe", "url": "javascript:alert(1)"},
            {"title": "", "url": "https://news.example/empty"},
            {"title": "Crash risks", "url": "https://news.example/b"},
        ]
    }
    rows = api._parse_articles(payload, 10)
    assert len(rows) == 2
    assert rows[0]["headline_sentiment"]["label"] == "positive"
    assert rows[0]["published_at"] == "20261024T000000Z"
    assert rows[1]["headline_sentiment"]["label"] == "negative"


def test_search_response_includes_source_and_summary(monkeypatch):
    monkeypatch.setattr(api, "_get_json", lambda query, limit: {
        "articles": [
            {"title": "Bullish adoption gains", "url": "https://news.example/a", "seendate": "20261024T000000Z"},
            {"title": "Market update", "url": "https://news.example/b", "seendate": "20261023T000000Z"},
        ]
    })
    result = api._search("bitcoin", 5)
    assert result["source"] == "GDELT DOC 2.0 public article search"
    assert result["count"] == 2
    assert result["sentiment_summary"]["label"] == "positive"
    assert result["sentiment_summary"]["confidence"] == "low"
    assert result["data_quality"]["limitations"]


def test_endpoint_classifies_provider_network_failure(monkeypatch):
    monkeypatch.setattr(api, "_search", lambda _query, _limit: (_ for _ in ()).throw(urllib.error.URLError("offline")))
    with pytest.raises(HTTPException) as caught:
        asyncio.run(api.news_sentiment(query="bitcoin", max_records=5))
    assert caught.value.status_code == 503
    assert caught.value.detail["error"] == "network_error"


def test_invalid_provider_payload_is_rejected():
    with pytest.raises(ValueError, match="Unexpected GDELT"):
        api._parse_articles([], 10)
