# CIN order-book liquidity diagnostics — development-only

The pure function `assess_order_book(snapshot, ...)` reads a **caller-supplied** Level 2 snapshot. Required fields: `symbol`, `source`, timezone-aware `observed_at`, and non-empty ordered `bids` and `asks`, each level being `[price, base_quantity]`. Maximum 200 levels per side. Strictly descending bid prices and ascending ask prices are required, with positive finite prices and sizes. Locked/crossed books and future timestamps are invalid.

The module computes mid-price bid/ask spread in basis points and total reported quote notional on each side; both sides must independently exceed a configurable minimum and the spread must meet a configurable maximum. Snapshots older than 30 seconds are never considered sufficient. These are configurable **research gates**, not an estimate of executable fill, slippage or price impact. Snapshot source labels are not independently verified, nor is this module connected to an exchange or the live shortlist. Exchange/trading-pair identity and depth completeness must be independently corroborated before production use.

Defaults (30 bps maximum spread and 10,000 quote units minimum depth per side) are provisional and **not validated universal thresholds**; thresholds should be market-specific and backtested. Depth sums use the units of the quoted currency and are not universally comparable across pairs.

Offline regression tests: `python -m unittest tests.test_cin_shortlist_orderbook_liquidity -v`. This module makes no network requests, handles no private credentials, does not execute or manage orders, and is not mounted in production.
