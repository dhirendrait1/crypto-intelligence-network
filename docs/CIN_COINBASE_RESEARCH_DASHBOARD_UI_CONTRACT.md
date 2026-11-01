# CIN Coinbase research UI contract — draft, not live

This frontend milestone is stacked on the cinematic React dashboard PR #202; its API contract was implemented separately in draft PR #201. Both remain unmerged and must be reconciled before release.

The Research tab uses a fail-closed display adapter. The explicit `VITE_CIN_COINBASE_RESEARCH_UI_ENABLED=true` UI flag defaults off. Even when enabled, the current App passes no payload and makes **no request** to the protected `/research/coinbase/market-eligibility` staging route.

The view accepts an optional injected v1 payload only for offline tests or a **future approved server-side gateway**. The operator bearer token must never enter browser JavaScript, Vite environment variables, URL query strings or public logs. No browser-side staging request, credentials, API route mount, Render/Cloudflare changes or paid services are introduced.

The adapter checks the exact version, Coinbase provider identity, BTC-USD/ETH-USD product allowlist (and optional expected identity), rejected/insufficient_data status, caller-supplied unverified provenance, false shortlist approval and execution flags, boolean book_requested, four typed evidence fields, and rejects any positive liquidity/security/risk gate. Unknown schemas, untrusted data and contradictory fields fail closed.

A disabled UI reports DISABLED; missing data reports NOT CONNECTED; 404 reports NOT MOUNTED; 429 reports RATE LIMITED; other HTTP failures report UNAVAILABLE. No implicit refresh or retry. Raw provider reason/diagnostics are never rendered. `data_reliable=true` is only labelled Preliminary, not independently verified. The research endpoint supplies no verified price, timestamp or confidence score; none is fabricated.

Tests: `cd frontend && npm install --no-audit --no-fund && npm run typecheck && npm test && npm run build`. Frontend CI is configured on pull requests, but passing tests do not establish live-provider operation or deployed dashboard functionality.

**Release gates:** reconcile PR #201, PR #202 and their ancestor stacks; independent provenance and factor verification; authorized server-side identity gateway, distributed quotas, caching, CORS and abuse review; Android accessibility and integration checks; explicit deployment approval. CIN remains research-only: no trading, orders, wallets or fund movement.
