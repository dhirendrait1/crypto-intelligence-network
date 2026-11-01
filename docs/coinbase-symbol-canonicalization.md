# Coinbase symbol parsing and canonical product mapping

CIN's Coinbase fallback accepts only the existing explicit concatenated-symbol input contract and converts it into a Coinbase Exchange product identity before any catalogue or candle request.

## Canonical mapping

- Input symbols must be non-empty, uppercase, and free of surrounding whitespace.
- The parser recognizes only the supported quote suffixes, preferring the longer `USDT` suffix before `USD`.
- Coinbase fallback is USD-quoted only. A USDT symbol is rejected; it is never silently rewritten to USD.
- A supported input such as `BTCUSD` maps to product ID `BTC-USD`, base `BTC`, quote `USD`.
- Numeric-leading asset codes remain bounded by the parser's explicit asset-code grammar; for example, `1INCHUSD` maps to `1INCH-USD`.
- Hyphenated, slash-separated, underscored, lowercase, padded, unsupported-quote, and ambiguous/incomplete symbols are rejected rather than normalized heuristically.

## Request boundary

The canonical identity is produced by one Coinbase-specific helper and then passed unchanged to product-catalogue verification and URL path encoding. Catalogue verification still independently confirms that the exact product ID and base/quote fields match. No ticker alias, stablecoin equivalence, or cross-quote substitution is inferred.

## Regression coverage

Offline tests cover BTC/USD and ETH/USD mappings, numeric-leading asset codes, an asset code ending in the text `USD`, explicit USDT rejection, and malformed formatting. These tests validate deterministic mapping only; they do not claim live product availability.
