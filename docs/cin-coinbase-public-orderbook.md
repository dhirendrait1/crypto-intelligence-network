# Coinbase public order-book ingestion (draft, unmounted)

CIN reads Coinbase's documented **public** Advanced Trade market book endpoint:

`GET https://api.coinbase.com/api/v3/brokerage/market/product_book?product_id=BTC-USD&limit=50`

The public route does not require an API key. See [Coinbase public product-book documentation](https://docs.cdp.coinbase.com/api-reference/advanced-trade-api/rest-api/public/get-public-product-book).

`cin_coinbase_public_orderbook.fetch_coinbase_public_book` is a bounded, synchronous, read-only adapter: it accepts only canonical upper-case `BASE-QUOTE` IDs, makes one HTTPS GET to the fixed hostname/path, rejects redirects and mismatched product IDs, limits input size and depth, and validates the returned `pricebook` with `product_id`, `time`, `bids`, `asks`. Each price level contains decimal-string `price` and `size`; source values are not rounded or rewritten.

It passes price/quantity rows to CIN's existing depth/spread validator and returns diagnostics with explicit provenance. Missing/invalid content fails closed. Network connection and provider endpoint ownership are distinct from independent proof of current executable liquidity: reported price levels, even from a fixed public route, do **not** establish future fills, slippage or perfect market completeness.

**Release gates:** The module is NOT mounted in the live API, and no scheduled polling is enabled. Confirm actual live payload schema and availability in staging, provider quotas, requested instrument status and market/quote identity, bounded failure modes, and source/factor confidence before using it to authorize any positive shortlist liquidity gate. No trading/order calls, wallets, keys, funds or paid infrastructure.

Offline tests: `python -m unittest tests.test_cin_coinbase_public_orderbook -v`.

## Documented response-envelope compatibility

Coinbase's public product-book schema also permits the optional top-level string fields `last`, `mid_market`, `spread_bps` and `spread_absolute` alongside the required `pricebook`. CIN now accepts these documented fields with bounded string validation, but derives spread and depth solely from validated order-book levels, not from optional provider claims. Unknown top-level fields and missing `pricebook` still fail closed.

A direct live request from the current development execution environment could not be completed because external DNS resolution was unavailable. Documentation-backed contract validation and mocked CI tests **are not** evidence of a successful live Coinbase ingestion. Validate actual responses in an authorized network-enabled staging environment before mounting the adapter in a live API.

## GitHub-run live verification (2026-11-01 UTC)

A GitHub-hosted runner successfully completed a **single public GET** to Coinbase's BTC-USD product-book endpoint using draft commit `9f74cf15620bd1c9e18c066cc28db2264dd740e8`.

- [Live Coinbase smoke workflow #1](https://github.com/dhirendrait1/crypto-intelligence-network/actions/runs/41353664038), job `124989021055`.
- The redacted output reported `status=pass`, `snapshot_fresh=true`, `age_seconds=0`, `bids=50`, `asks=50` and `production_activated=false`.
- The mock-only smoke regression suite ran **6 tests successfully** in the same job.
- Four other CIN PR workflows for the same commit also completed successfully (Automated Tests #1335; Screening #1230; Evidence Ingestion #1204; Technical Analysis #1204).

This is evidence of **one successful live response and adapter compatibility at that time**, not continuous provider reliability, completeness across other markets or proof of executable fill liquidity. The optional research router and adapter remain unmounted; no Render/Cloudflare deployment, trading endpoint or paid service was activated. The workflow's live step is explicitly nonblocking, so a future workflow-level green check must not be interpreted as a provider pass without reading its redacted `status` line.
