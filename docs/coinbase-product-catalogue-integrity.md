# Coinbase product-catalogue integrity

CIN's Coinbase candle adapter verifies the public `/products` catalogue before it requests a candle page.

## Acceptance rules

- The catalogue response must be a JSON list.
- The requested product is selected by its exact product `id`; no symbol alias, case-folding, or quote-asset substitution is used.
- Exactly one record may carry the requested product identifier. Duplicate identifiers are ambiguous and are rejected even if one duplicate appears valid.
- The selected record's `base_currency` and `quote_currency` must exactly match the requested market identity. Missing, empty, non-string, or conflicting asset values fail closed.
- Product eligibility additionally requires an explicitly recognized `online` status and a boolean `trading_disabled` value set to `false`. Missing or unknown status metadata is not treated as availability.
- Unrelated malformed catalogue entries are not used as matches; they do not override a separate, unique, exact target record.

## Failure behavior

A missing target product is treated as unavailable. A malformed catalogue envelope, duplicate target identifier, or invalid target identity is treated as malformed provider data. In every rejection case, the adapter stops before issuing the candle request. It does not select the first duplicate, infer asset identity from a ticker string, or map USD and USDT as interchangeable quote assets.

## Regression coverage

Offline mocked tests cover exact product selection, base/quote mismatch, duplicate IDs, missing products, status and trading-eligibility metadata, malformed catalogue envelopes, invalid target asset identity types/values, conflicting duplicates in either record order, and unrelated malformed records. These tests validate the adapter's fail-closed contract; they do not establish live Coinbase availability or constitute a production activation.
