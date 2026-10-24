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
