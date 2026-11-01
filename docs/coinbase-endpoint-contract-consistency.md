# Step 196 — Coinbase endpoint-specific response-contract consistency

The shared successful-response envelope check establishes only that Coinbase returned a top-level JSON array. It does not establish that the array's elements satisfy the contract of the endpoint that produced them.

## Product catalogue

The products endpoint is a collection of product objects. Every record must be an object with a non-empty string `id`, and product identifiers must be unique across the returned catalogue. A malformed unrelated record is not silently skipped: it makes the catalogue response ambiguous and is rejected.

An empty catalogue is structurally valid but contains no requested product. The existing product-eligibility path reports the requested product as absent; it does not reinterpret the empty collection as a transport failure or continue to candle retrieval.

## Candle pages

The candles endpoint is an array of six-field candle rows. Its existing page validator remains responsible for row cardinality, types, timestamp order, page limits, and interval rules. An empty candle page is structurally valid: a bounded time window may contain no returned rows. However, the complete requested snapshot still requires usable candle data; if all requested pages yield no candles, the fetch operation fails closed rather than returning an apparently successful empty market snapshot.

## Scope

This step adds endpoint-specific product-catalogue record validation and offline regression coverage for empty collections, malformed catalogue entries, duplicate identifiers, and empty candle pages. It does not alter pagination, timestamp normalization, row ordering, OHLCV calculations, fallback selection, or the public response schema. No candle is synthesized or repaired. All access remains public and read-only; no account endpoints, API keys, orders, wallet access, merge, deployment, or production activation are involved.
