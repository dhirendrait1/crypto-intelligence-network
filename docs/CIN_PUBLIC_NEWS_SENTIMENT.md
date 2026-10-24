# CIN Public News Search and Headline Sentiment

## Endpoint

`GET /news-sentiment?query=bitcoin&max_records=20`

Uses the public [GDELT DOC 2.0 API](https://api.gdeltproject.org/api/v2/doc/doc) to retrieve indexed news articles. No API key is configured or required by this module.

## Output contract

- CIN retrieval timestamp is separate from each provider-supplied article time.
- Articles are deduplicated by URL and only HTTP(S) links are accepted.
- Each headline includes a small, transparent positive/negative keyword-lexicon result.
- The response includes article counts by headline label and a coarse aggregate score.

## Interpretation and limitations

This is **headline-only heuristic sentiment**, not a trained financial model. The lexicon does not understand negation, sarcasm, context, or entity-specific meaning. Confidence is intentionally low. News coverage and publication timestamps depend on GDELT indexing. It is not X, Reddit, Telegram, or other social-platform sentiment, and it does not establish market direction.

Provider failures return structured HTTP/network/invalid-response errors. Tests mock payloads and failures; live GDELT availability and deployed endpoint behavior remain unverified until a network-enabled smoke test is possible.


## Provider timestamp semantics

GDELT's `seendate` is the provider's seen/indexing time and is **not guaranteed to be the article's original publication time**. New consumers should use `provider_seen_at`, `provider_seen_at_utc`, and `provider_seen_at_validation_status`. The older `published_at*` fields remain as compatibility aliases and mirror the same values; they must not be treated as verified publication timestamps.

Timestamps more than 60 seconds ahead of CIN's UTC clock are labeled `future_dated` while preserving the normalized value for diagnosis. Invalid, timezone-naive, and missing values remain separately classified. These checks validate timestamp format and obvious future skew; they do not verify the publisher's actual publication time.


## Aggregate timestamp-quality metadata

The response exposes `data_quality.provider_timestamp_quality_counts` with counts for `valid`, `missing`, `invalid_timezone`, `invalid`, and `future_dated` provider seen times. These counts refer to GDELT indexing/seen times and do not verify original publication time. For backward-compatible behavior, the headline sentiment aggregate still includes every accepted article regardless of timestamp status; consumers must inspect the quality counts before using timestamps for time-sensitive evidence.
