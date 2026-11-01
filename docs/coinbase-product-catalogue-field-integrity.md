# Step 197 — Coinbase product-catalogue field integrity

The Coinbase products collection is not accepted solely because each entry is a JSON object with a unique product ID. CIN now validates the typed metadata required to establish the requested market identity and determine whether candle retrieval is eligible.

Each catalogue record must contain:
- `id`: non-empty string (identity uniqueness remains covered by the preceding step).
- `base_currency`: non-empty string.
- `quote_currency`: non-empty string.
- `status`: one of the explicitly recognized values `online`, `offline`, or `delisted`.
- `trading_disabled`: a JSON boolean; numeric and string lookalikes are rejected.

Missing, null, blank, or incorrectly typed required fields are malformed provider data. Unknown status values are not treated as online. The requested product's base/quote identity and online/enabled eligibility checks continue to run after the catalogue records pass structural validation.

Offline regression tests cover valid typed records, invalid base/quote fields, missing or unknown status, and non-boolean trading-disabled flags. Existing tests for empty catalogues, malformed records, duplicate IDs, and envelope validation remain in place.

This step does not add new provider requests or change pagination, candle row parsing, timestamp handling, OHLCV normalization, fallback policy, or public API output. It uses only public read-only Coinbase data. No trading, orders, wallet access, private credentials, merge, deployment, or production activation.
