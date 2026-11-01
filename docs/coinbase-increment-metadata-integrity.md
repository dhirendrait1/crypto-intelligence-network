# Step 198 — Coinbase increment metadata integrity

Coinbase product-catalogue records must provide both `base_increment` and `quote_increment` as non-empty decimal strings. CIN parses these values with the existing Decimal-based parser to avoid binary floating-point conversion during validation.

Each increment must be finite and strictly greater than zero. Missing fields, nulls, JSON numeric values, booleans, blank strings, malformed decimal strings, NaN, infinities, zero, and negative values are rejected as malformed provider metadata.

The source decimal strings are not rounded, rewritten, or used to alter candle values. This check validates the provider's declared quantity increments only; it does not quantize, rescale, repair, or otherwise transform market data.

Offline regression coverage includes valid fractional increments, wrong JSON types, malformed decimal strings, non-finite values, zero, and negative values. Existing product identity, status, and trading-disabled checks remain unchanged.

No new provider requests or public API behavior are introduced. Public read-only market data only; no trading, order execution, wallet access, credentials, merge, deployment, or production activation.
