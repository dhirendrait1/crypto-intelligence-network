# CIN shortlist liquidity reconciliation — trust boundary

`cin_shortlist_liquidity_reconciliation.reconcile_liquidity` accepts existing normalized market-data evidence and caller-supplied order-book snapshots without accessing networks, credentials, accounts or execution systems.

**Identity**: the market-data `symbol` and `currency` must exactly match the L2 book's `BASE-QUOTE` identifier; a BTC-USD book cannot silently be used to validate BTC-USDT. Quote depth is expressed in that book's quote currency, not universally comparable dollars.

**Safety**: stale market snapshots, stale order books, wide spreads and insufficient per-side quoted depth produce a **negative** liquidity gate. A caller-supplied L2 book passing all numerical thresholds **does not produce a positive liquidity gate**: it remains unknown because a source label does not authenticate its provider, completeness or market identity. The security and risk gates also remain unknown.

The next distinct requirement before positive gating is a provider-verified, read-only L2 ingestion adapter with independently established instrument identity, freshness, schema and provenance. Never substitute self-declared strings such as `official` or `verified` for authentication. This is not an execution, order-routing or slippage-estimation module.

Offline tests: `python -m unittest tests.test_cin_shortlist_liquidity_reconciliation -v`. No Render/Cloudflare production activation or live provider fetch is part of this change.
