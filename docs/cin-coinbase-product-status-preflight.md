# CIN Coinbase Public Product Status — read-only shortlist preflight

Coinbase documents its public `GET /api/v3/brokerage/market/products/{product_id}` endpoint without authentication. The response contains `product_id`, base/quote currency identifiers, `status`, `product_type`, and flags including `is_disabled`, `trading_disabled`, `view_only` and `auction_mode`.

`cin_coinbase_public_product_status.py` requests a fixed Coinbase public HTTPS product URL using **GET** only. It enforces request identity, exact returned product/base/quote identifiers, strict flag types, a bounded response and no redirected destinations. The deliberately conservative research check requires `status=online`, `product_type=SPOT`, and all four restriction flags false. Unknown or missing metadata is rejected, not silently assumed active. These fields describe *market availability for research*, not CIN permission to trade.

`cin_coinbase_status_shortlist_pipeline.py` runs the public product-status preflight **before** calling the previously validated public order-book integration. Offline, delisted, restricted or non-spot products short-circuit the order-book request. Even when the product is active, independent market-row provenance, full order-book completeness, source confidence, security, and risk remain separate, unresolved eligibility gates. The pipeline never changes a missing/unknown positive liquidity gate to true.

Offline tests:
```bash
python -m unittest tests.test_cin_coinbase_public_product_status tests.test_cin_coinbase_status_shortlist_pipeline -v
```

This code is **unmounted**, draft and undeployed. Product-status calls are public, read-only, no authorization headers, no credentials, no orders, no wallets, no funds and no paid services. Before staging or production enablement, validate current live product responses, bound network operations, and assess the complete release gates.

Official reference: https://docs.cdp.coinbase.com/api-reference/advanced-trade-api/rest-api/public/get-public-product
