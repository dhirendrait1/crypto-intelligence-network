# Coinbase read-only order-book to shortlist eligibility — integration boundary

The development-only function `evaluate_coinbase_liquidity(market_row)` is the first concrete wiring of CIN's fixed HTTPS Coinbase public product-book adapter into the shortlist's market/liquidity evidence path.

1. Validate the normalized market row and preserve its uppercase `BASE-QUOTE` identity.
2. Make **one** public Coinbase market-product-book GET through `fetch_coinbase_public_book` (no credentials or order endpoints).
3. Require explicit provider, product, endpoint, GET method, public unauthenticated route, provenance and disabled execution flags.
4. Revalidate supplied Coinbase book levels, timestamp, depth, spread, and market pair against the market row.
5. Return the existing fail-closed shortlist evidence schema plus recorded acquisition facts, **never** a buy/sell recommendation.

**Important:** Public-provider request success alone does not independently authenticate the separate normalized market-row source, establish market/product active status, certify order-book completeness, or guarantee executable liquidity. A numerically healthy Coinbase book remains an *unknown* positive liquidity gate until those checks exist. Stale/insufficient book evidence is a negative gate; security and risk gates remain unknown.

Offline contract tests: `python -m unittest tests.test_cin_coinbase_shortlist_integration -v`. No production router is mounted, no Render/Cloudflare deployment, paid service, wallet, credentials, funds or trade execution are involved. Next release gates: verified market/product identity and status; market data from a trusted provider source rather than caller assertions; dashboard API contract/staging; reviewer-approved integration.
