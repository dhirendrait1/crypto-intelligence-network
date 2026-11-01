# CIN Coinbase dashboard research API — staging contract only

`cin_coinbase_dashboard_research_api.router` defines `POST /research/coinbase/market-eligibility`, but **the router is NOT included in the live CIN app, Render patch or any default application**. Registering it in a separately reviewed staging application is required, AND the environment flag `CIN_COINBASE_RESEARCH_ENABLED=1` must be exactly set. Every other value returns 404 before invoking any public provider. Never set this flag on production until reviewed and approved.

Request schema:
```json
{
  "market": {
    "id": "bitcoin",
    "symbol": "BTC",
    "currency": "USD",
    "price": 100.5,
    "last_updated": "2026-11-02T00:00:00Z",
    "freshness_status": "fresh",
    "analysis_eligible": true,
    "total_volume_24h": 12345.0
  }
}
```

**This is an illustrative synthetic payload, not a live quote**; the timestamp must be recent at the time of any real test. Only BTC-USD and ETH-USD are permitted during this milestone, and no user-defined URL is accepted. When explicitly enabled, the route invokes the already implemented public Coinbase product-status preflight and public order-book evaluation, then emits a bounded dashboard contract without raw bid/ask levels, provider exception text, or proprietary credentials.

Response uses `schema_version=cin-coinbase-market-eligibility-v1`, `status` (only `rejected` or `insufficient_data`), `product_id`, `market_status`, `book_requested`, `eligibility_evidence`, `shortlist_approved=false` and `execution_enabled=false`. Product/provider errors return sanitized 503; invalid market payloads return 422; unsupported pairs return 400. Positive shortlist approval remains prohibited because independent market-row and factor evidence is not yet established.

The route is **not authenticated**, so do not expose it on a public internet host by merely enabling its environment flag. A future deployment needs strong authentication, provider call rate limiting, response cache/budget, and staging review. It is not a trading API; it cannot place or route orders, access wallets, or move funds.

Offline HTTP tests: `python -m unittest tests.test_cin_coinbase_dashboard_research_api -v`. No changes to production deployment.
