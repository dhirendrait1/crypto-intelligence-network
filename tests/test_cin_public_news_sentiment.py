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
    assert rows[0]["published_at_utc"] == "2026-10-24T00:00:00Z"
    assert rows[0]["published_at_validation_status"] == "valid"
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



def test_empty_news_result_is_unavailable_not_neutral_claim(monkeypatch):
    monkeypatch.setattr(api, "_get_json", lambda _query, _limit: {"articles": []})
    result = api._search("a uniquely narrow query", 5)
    assert result["count"] == 0
    assert result["sentiment_summary"]["label"] == "unavailable"
    assert result["sentiment_summary"]["score"] is None
    assert "not that news or sentiment is absent globally" in result["data_quality"]["limitations"][-1]


def test_endpoint_classifies_provider_rate_limit(monkeypatch):
    def fail(_query, _limit):
        raise urllib.error.HTTPError("https://example.invalid", 429, "rate limited", {}, None)

    monkeypatch.setattr(api, "_search", fail)
    with pytest.raises(HTTPException) as caught:
        asyncio.run(api.news_sentiment(query="bitcoin", max_records=5))
    assert caught.value.status_code == 503
    assert caught.value.detail["error"] == "http_error"
    assert caught.value.detail["http_status"] == 429


def test_endpoint_rejects_whitespace_only_query_before_provider_call(monkeypatch):
    def unexpected_search(*_args):
        raise AssertionError("blank query must be rejected before provider access")

    monkeypatch.setattr(api, "_search", unexpected_search)
    with pytest.raises(HTTPException) as caught:
        asyncio.run(api.news_sentiment(query="   ", max_records=5))
    assert caught.value.status_code == 422



@pytest.mark.parametrize("failure", [RuntimeError("unexpected provider response"), TypeError("unexpected provider payload"), AttributeError("unexpected parser state"), Exception("unexpected generic provider failure")])
def test_endpoint_sanitizes_unexpected_provider_response_errors(monkeypatch, failure):
    def fail(_query, _limit):
        raise failure

    monkeypatch.setattr(api, "_search", fail)
    with pytest.raises(HTTPException) as caught:
        asyncio.run(api.news_sentiment(query="bitcoin", max_records=5))

    assert caught.value.status_code == 502
    assert caught.value.detail["error"] == "invalid_response"
    assert caught.value.detail["message"] == "Public news provider response was invalid."
    assert "unexpected provider response" not in str(caught.value.detail)


@pytest.mark.parametrize(
    "url",
    [
        "https://",
        "https:///missing-host",
        "https://user:secret@news.example/article",
        "https://news.example/has space",
        "https://news.example/report\nnewline",
        "https://news.example/report\ttab",
        "https://news.example/report\x7fdel",
        "ftp://news.example/article",
        "https://news.example:notaport/article",
        "https://news.example:99999/article",
        "javascript:alert(1)",
    ],
)
def test_parse_articles_rejects_malformed_or_credentialed_urls(url):
    rows = api._parse_articles(
        {"articles": [{"title": "Article", "url": url}]},
        10,
    )
    assert rows == []


def test_parse_articles_accepts_valid_http_and_https_urls():
    rows = api._parse_articles(
        {
            "articles": [
                {"title": "HTTP article", "url": "http://news.example/a"},
                {"title": "HTTPS article", "url": "https://news.example/b"},
            ]
        },
        10,
    )
    assert [row["url"] for row in rows] == [
        "http://news.example/a",
        "https://news.example/b",
    ]


def test_article_timestamp_validation_preserves_raw_provider_value():
    rows = api._parse_articles(
        {
            "articles": [
                {"title": "Malformed time", "url": "https://news.example/a", "seendate": "not-a-date"},
                {"title": "Naive time", "url": "https://news.example/b", "seendate": "2026-10-24T00:00:00"},
                {"title": "Missing time", "url": "https://news.example/c"},
            ]
        },
        10,
    )
    assert rows[0]["published_at"] == "not-a-date"
    assert rows[0]["published_at_utc"] is None
    assert rows[0]["published_at_validation_status"] == "invalid"
    assert rows[1]["published_at_utc"] is None
    assert rows[1]["published_at_validation_status"] == "invalid_timezone"
    assert rows[2]["published_at"] is None
    assert rows[2]["published_at_validation_status"] == "missing"
