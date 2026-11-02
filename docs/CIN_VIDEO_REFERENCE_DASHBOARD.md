# CIN video-reference dashboard — cinematic command center

Status: **draft, feature-branch frontend only; not merged or deployed**.

## Reference analysis (user-provided 27.84-second, 720×900 video)

The reference is a vertically presented, highly dense institutional terminal. Its stable composition has a narrow system/header strip, multiple compact metric/market panels across the upper quarter, a large animated toroidal particle mesh with source-to-network connectors in the central ~half, a pair of information-dense lower panels, and tiny tabular/timestamp readouts. Primary palette: near-black navy, steel blue, teal/cyan, muted gold, and occasional red. Small labels use uppercase tracking and tightly bordered cells. Throughout the video the torus revolves/morphs while adjacent plots and values update.

The source video also contains execution, fills, settlement, bets and other trading-related affordances. **Those are intentionally excluded**. CIN is a read-only crypto research, analysis, monitoring and alerting project.

## CIN adaptation delivered

- Compact CIN identity/status command bar and four status cards (BTC, ETH, data integrity, alerts).
- Upper market-structure motif with **NO CANDLES / NO MARKET DATA** label and an integrity inspector with clearly unverified checks.
- Center geometric torus inspired by the particle-network aesthetic. It uses deterministic procedural geometry and **is not a representation of market data, provider topology, correlations, trading signals, or AI reasoning**.
- Surrounding read-only module tiles: market data, technical analysis, coin screening, news sentiment, alert intelligence, source reliability.
- Bottom provider provenance ledger and empty research-observability timeline.
- Explicit price/score/alert/freshness unknown values instead of synthetic or guessed live data.
- Mobile breakpoints, reduced-motion preference, and a keyboard-accessible Pause/Resume motion button.
- Preserves the existing gated MarketsScreen and user-initiated public-market-data loading behavior. No new fetches from Overview other than the pre-existing optional health/readiness checks.
- No new npm dependencies or paid services.

## Acceptance and follow-ups

1. Run frontend typecheck, Vitest, and build against the exact PR head.
2. Verify pixel/layout behavior on desktop and Android viewport widths of 360px, 412px, 768px, and 1440px.
3. Confirm no market values are shown without validated price/quote identity, source identity, data freshness, and response-schema checks.
4. Keep the Markets feature gate disabled by default. Any future live Overview tiles must use explicit validated contracts, fail closed, and display per-field provenance.
5. Complete a reduced-motion and keyboard/screen-reader review.
6. Reconcile the existing stacked frontend dependency PRs before integration to main.

No merge, CI pass, actual service integration, deployment or production activation is claimed by this design implementation. No trading, order execution, order management, wallet control, keys, fund movement, or private data.
