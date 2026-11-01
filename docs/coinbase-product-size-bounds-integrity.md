# Step 199 — Coinbase product minimum and maximum size metadata

CIN validates the four size-bound fields in each Coinbase product-catalogue record:
- `base_min_size`
- `base_max_size`
- `quote_min_size`
- `quote_max_size`

Each field must be present as a non-empty decimal string. Values are parsed with the existing Decimal-based parser and must be finite and strictly positive. The minimum may equal the maximum, but it must never exceed the corresponding maximum.

The base-size and quote-size pairs are checked independently. No cross-unit comparison is performed between base and quote quantities. The source strings are not rounded, quantized, or rewritten, and these metadata checks do not transform candle values.

Offline regression coverage includes valid bounds, missing and incorrectly typed fields, malformed/non-finite/non-positive values, and inverted minimum/maximum pairs. The validation is performed as part of the existing read-only catalogue integrity check.

No provider request, pagination behavior, timestamp handling, candle normalization, fallback policy, or public API output is intentionally changed. Public read-only data only; no trading, order execution, wallet access, credentials, merge, deployment, or production activation.
