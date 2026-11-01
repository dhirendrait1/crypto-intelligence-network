# CIN PR dependency audit

Snapshot: 2026-11-01. Main: `8a589ec15a713a6d639a484522ee7a552f6f382d`.

## Findings

- 186 open PRs: 158 draft, 28 non-draft; 45 target main and 141 target another open PR branch.
- All 141 branch targets resolve to an open PR. The declared dependency graph is acyclic.
- 133 parent-child comparisons contain the current parent head; eight have diverged. PR #9 additionally trails main by five commits.
- 75 exact PR head SHAs have reported check runs, all successful; 111 report zero check runs. This is not evidence that all expected suites ran. Check job totals and URLs are in the JSON evidence.
- The main CIN test workflow on #199 filters pull_request branches to main; this excludes intermediate stack targets. Add trusted stack/integration targets or run workflow_dispatch against the selected heads before integration.
- Source and check metadata were read through GitHub. No local tests, conflict simulation, live-provider acceptance, merging, retargeting, or deployment were performed. Successful nonblocking provider-probe jobs do not establish successful live-provider acceptance.

## Dependency map

Arrows mean parent before child; numeric ranges below mean every consecutive PR.

- Main → #66 → #70 → #71 → … → #88. From #88: #89 → … → #93 (Markets diagnostics), and #94 → … → #199 (provider validation).
- #87 → #202 (Overview dashboard). #202 does not contain current #88: the two have diverged. Integrate both descendants deliberately.
- Main → #16 → #19; #16 → #61 → #62; #16 → #63.
- Main → #57 → #58 → #60.
- Main → #54 → #55.
- Main → #49 → #50 and #51.
- Main → #44 → #46.
- All other PRs target main directly. That target does not establish semantic independence; see overlap review and full inventory.

## Repair parent drift first

Merge the current parent into an isolated candidate child branch, or rebase with review; preserve existing branch history unless a separate decision authorizes rewriting it. Re-run checks after every resulting change. Repair lower ancestors before descendants.

| Child | Parent | Child-only commits | Missing parent commits |
| --- | --- | ---: | ---: |
| #19 | #16 | 1 | 2 |
| #50 | #49 | 9 | 7 |
| #51 | #49 | 5 | 7 |
| #55 | #54 | 4 | 1 |
| #61 | #16 | 5 | 2 |
| #62 | #61 | 8 | 4 |
| #87 | #86 | 5 | 1 |
| #89 | #88 | 24 | 6 |

PR #9 separately has one unique commit and is five commits behind main. Divergence is an ancestry fact, not proof of a textual merge conflict.

## Integration checklist and order

1. Preserve this snapshot and current branch heads; refresh PR/head state before starting integration. Do not equate PR numbers with a universal merge order.
2. Land the time-relative freshness fixture from #200 in the integration candidate first. #201 touches the same test file and has diverged from #200 (44 commits unique to #201, two unique to #200); compare the actual hunks before selecting one fixture fix.
3. Review #66 as the foundation of the large stack. Its title understates its 42-file scope: evidence repository/schema, cross-source evidence, fundamentals/news/derivatives changes, route patch, tests and roadmap updates. Review those as distinct acceptance areas.
4. Integrate #66 → #70 → #71–#86. Update #87 with current #86 (one missing commit), validate, then integrate #88. These are dependency order instructions, not release approval.
5. From that common base reconcile #89 with current #88 (six missing commits), then #90–#93. Separately integrate #94–#199 sequentially or as a reviewed aggregate preserving all unique changes. The #199 head contains current #66 but has diverged from #93; it is not a substitute for the diagnostics branch.
6. Reconcile #202 with the updated #87/#88 lineage and chosen #89–#93 frontend diagnostics. #202 currently has one successful frontend check job, not full backend integration acceptance. Run typecheck, unit tests, production build and Android review on the combined result.
7. Evaluate #201 as a separate research feature. Keep its API unmounted/disabled until its documented staging prerequisites are met. It is not the parent of #202 and does not supply the Markets stack automatically.
8. Keep monitoring (#57/#58/#60), alerts (#16/#19/#61/#62/#63), forecast persistence (#67), and screening/provider migration (#68/#69) as separate integration lanes until their shared modules/contracts are reconciled.
9. Run all applicable backend and frontend suites against the final candidate, including scaffold extraction/router registration. Record exact head, expected job set, conclusions and live-check limitations. Do not close earlier PRs as duplicates until unique commits/hunks/tests are accounted for.
10. Publish a candidate review with included/excluded PRs, outstanding acceptance gates and rollback steps. Main currently enables Render autoDeploy: merging into main can deploy. This audit does not authorize a release or change that setting.

## Semantic overlap requiring review

| Area | PRs | Required reconciliation |
| --- | --- | --- |
| Candle provider/provenance | #7/#8/#23/#27/#49/#50/#51/#53/#54/#55 and #94–#199 | Select a combined provider policy; preserve identity, quote, provenance and boundary tests. #54 contains current #53; it has diverged from current #49. |
| Monitoring | #42/#44/#45/#46/#48/#57/#58/#59/#60 | #57 contains #44 and #46; #59 contains #57 and #58. #42 and #48 diverge from #57. Compare unique contract/test changes before retiring any branch. |
| Dashboard implementations | #59 and #71–#93/#202 | #59 adds dashboard/index.html; #202 changes React frontend. #59 and #66 diverge; the large React stack rooted at #66 does not automatically include #59. Choose the active UI and retain needed monitoring contracts. |
| Forecasts and alerts | #16/#35–#39/#67 | #67 contains current #38, but alert and forecast persistence modify shared ledger/test paths. Reconcile storage schema, authentication and migrations. #35 diverges from #16. |
| Alert recovery policy | #16/#19/#61/#62/#63 | #61 misses two parent commits; #62 misses four #61 commits; #19 also misses two #16 commits. #62 describes automatic post-lease retry; #63 changes ambiguous sends to uncertain/manual resolution. Update tests and choose one consistent delivery policy. #61 does not contain current #19. |
| Market overview/provider migration | #29/#31/#64/#66/#69 | Preserve freshness/provenance with Coinbase field/coverage semantics. Re-run older provider-specific tests against the selected adapter. |
| Screening | #26/#28/#52/#65/#68 | Refresh cache/fallback test expectations for CoinPaprika-only policy; do not blindly retain assumptions about two-provider failure. |
| Deployment routing/CI | #8/#44/#45/#49/#52/#54/#57/#59/#66/#67 | Reconcile patch_cin_metadata_fixed.py, route tests and workflows rather than accepting the newest whole file. |
| Status documentation | #8/#16/#17/#30/#32–#34/#66/#200 | Replace stale checkpoints with final candidate evidence; retain unique acceptance requirements. |

These are observed shared paths, documented behavior differences and targeted ancestry comparisons; they are not a completed line-by-line code review or proof that a PR is redundant.

## Verified ancestry reuse candidates

The following current heads are already ancestors of another open PR head. Their commit history is included, but later code may alter behavior. Review unique acceptance requirements before closing or superseding anything.

- #7 is contained in #8 (662 later commits).
- #53 is contained in #54 (4 later commits).
- #44 is contained in #57 (22 later commits).
- #46 is contained in #57 (16 later commits).
- #57 is contained in #59 (61 later commits).
- #58 is contained in #59 (56 later commits).
- #38 is contained in #67 (77 later commits).
- #66 is contained in #199 (594 later commits).

## Complete open PR inventory

Parent is the open PR whose head branch equals the target branch. Behind counts are against that parent's current head, or main for roots. Zero check runs means unverified here, not failed. The JSON includes full SHAs, changed paths, individual check names/URLs and targeted comparison evidence.

| PR | Title | Parent | Draft | Ahead / behind | Reported successful checks |
| --- | --- | --- | --- | --- | ---: |
| [#7](https://github.com/dhirendrait1/crypto-intelligence-network/pull/7) | Validate CIN market-data provenance and closed-candle analysis | main | yes | 6 / 0 | 4 |
| [#8](https://github.com/dhirendrait1/crypto-intelligence-network/pull/8) | Audit CIN architecture and clarify closed-candle analysis metadata | main | yes | 668 / 0 | none |
| [#9](https://github.com/dhirendrait1/crypto-intelligence-network/pull/9) | Document public candle fallback and verification limits | main | no | 1 / 5 | 4 |
| [#14](https://github.com/dhirendrait1/crypto-intelligence-network/pull/14) | Broaden CIN news RSS fallback with query-specific search | main | no | 7 / 0 | 4 |
| [#16](https://github.com/dhirendrait1/crypto-intelligence-network/pull/16) | Add durable CIN alert evaluation and optional Telegram delivery | main | no | 63 / 0 | 5 |
| [#17](https://github.com/dhirendrait1/crypto-intelligence-network/pull/17) | Reconcile CIN implementation tracker with current release state | main | yes | 4 / 0 | 4 |
| [#19](https://github.com/dhirendrait1/crypto-intelligence-network/pull/19) | Test concurrent CIN alert outbox claims | #16 | no | 1 / 2 | 4 |
| [#23](https://github.com/dhirendrait1/crypto-intelligence-network/pull/23) | Reject mismatched Coinbase quote markets in candle fallback | main | no | 2 / 0 | 4 |
| [#24](https://github.com/dhirendrait1/crypto-intelligence-network/pull/24) | Document CIN market-data provider audit and migration gates | main | no | 2 / 0 | 4 |
| [#25](https://github.com/dhirendrait1/crypto-intelligence-network/pull/25) | Define CIN coin-screening data contract before provider migration | main | yes | 2 / 0 | 4 |
| [#26](https://github.com/dhirendrait1/crypto-intelligence-network/pull/26) | Test CIN screening output order and rank semantics | main | yes | 2 / 0 | 4 |
| [#27](https://github.com/dhirendrait1/crypto-intelligence-network/pull/27) | Validate public candle interval boundaries | main | yes | 10 / 0 | 4 |
| [#28](https://github.com/dhirendrait1/crypto-intelligence-network/pull/28) | Test CIN screening provider timestamp boundaries | main | yes | 3 / 0 | 4 |
| [#29](https://github.com/dhirendrait1/crypto-intelligence-network/pull/29) | Test CIN market-data future timestamp tolerance | main | yes | 1 / 0 | 4 |
| [#30](https://github.com/dhirendrait1/crypto-intelligence-network/pull/30) | Refresh CIN release tracker after PR #11 merge | main | yes | 1 / 0 | 4 |
| [#31](https://github.com/dhirendrait1/crypto-intelligence-network/pull/31) | Fix precise market-data freshness boundary | main | yes | 2 / 0 | 4 |
| [#32](https://github.com/dhirendrait1/crypto-intelligence-network/pull/32) | Specify CIN cross-source conflict acceptance contract | main | yes | 1 / 0 | 4 |
| [#33](https://github.com/dhirendrait1/crypto-intelligence-network/pull/33) | Specify CIN verifiable evidence record contract | main | yes | 1 / 0 | 4 |
| [#34](https://github.com/dhirendrait1/crypto-intelligence-network/pull/34) | Specify CIN read-only alert rule contract | main | yes | 1 / 0 | 4 |
| [#35](https://github.com/dhirendrait1/crypto-intelligence-network/pull/35) | Add deterministic read-only CIN alert rule evaluator | main | yes | 2 / 0 | 4 |
| [#36](https://github.com/dhirendrait1/crypto-intelligence-network/pull/36) | Add deterministic CIN alert deduplication and cooldown helpers | main | yes | 2 / 0 | 4 |
| [#37](https://github.com/dhirendrait1/crypto-intelligence-network/pull/37) | Add deterministic CIN alert delivery state transitions | main | yes | 2 / 0 | 4 |
| [#38](https://github.com/dhirendrait1/crypto-intelligence-network/pull/38) | Add retrospective CIN forecast outcome evaluation | main | yes | 2 / 0 | 4 |
| [#39](https://github.com/dhirendrait1/crypto-intelligence-network/pull/39) | Add descriptive CIN forecast error scorecards | main | yes | 2 / 0 | 4 |
| [#40](https://github.com/dhirendrait1/crypto-intelligence-network/pull/40) | Define CIN mobile dashboard API-to-screen contract | main | yes | 1 / 0 | 4 |
| [#41](https://github.com/dhirendrait1/crypto-intelligence-network/pull/41) | Add deterministic CIN dashboard response-state helper | main | yes | 2 / 0 | 4 |
| [#42](https://github.com/dhirendrait1/crypto-intelligence-network/pull/42) | Add explicit CIN monitoring status aggregation | main | no | 2 / 0 | 4 |
| [#43](https://github.com/dhirendrait1/crypto-intelligence-network/pull/43) | Define CIN Android low-bandwidth and accessibility criteria | main | yes | 1 / 0 | 4 |
| [#44](https://github.com/dhirendrait1/crypto-intelligence-network/pull/44) | Add read-only CIN monitoring status API | main | yes | 14 / 0 | 4 |
| [#45](https://github.com/dhirendrait1/crypto-intelligence-network/pull/45) | Test CIN monitoring warning validation over HTTP | main | no | 13 / 0 | 4 |
| [#46](https://github.com/dhirendrait1/crypto-intelligence-network/pull/46) | Add deterministic CIN monitoring freshness evaluator | #44 | no | 6 / 0 | 4 |
| [#47](https://github.com/dhirendrait1/crypto-intelligence-network/pull/47) | Define source-specific CIN freshness policy | main | yes | 2 / 0 | 4 |
| [#48](https://github.com/dhirendrait1/crypto-intelligence-network/pull/48) | Add CIN source observation metadata contract | main | yes | 4 / 0 | 4 |
| [#49](https://github.com/dhirendrait1/crypto-intelligence-network/pull/49) | Add explicit market candle quote and provenance metadata helpers | main | yes | 18 / 0 | 4 |
| [#50](https://github.com/dhirendrait1/crypto-intelligence-network/pull/50) | Add market-candle provenance contract integration tests | #49 | yes | 9 / 7 | 4 |
| [#51](https://github.com/dhirendrait1/crypto-intelligence-network/pull/51) | Validate Kraken returned market identity before accepting candles | #49 | no | 5 / 7 | 4 |
| [#52](https://github.com/dhirendrait1/crypto-intelligence-network/pull/52) | Add offline CIN screening adapter contract tests | main | no | 4 / 0 | 4 |
| [#53](https://github.com/dhirendrait1/crypto-intelligence-network/pull/53) | Make Coinbase primary for exact USD-quoted market candles | main | no | 7 / 0 | 4 |
| [#54](https://github.com/dhirendrait1/crypto-intelligence-network/pull/54) | Integrate quote-safe market candles with provenance metadata | main | yes | 11 / 0 | 4 |
| [#55](https://github.com/dhirendrait1/crypto-intelligence-network/pull/55) | Validate Coinbase public candle timestamps and OHLCV | #54 | yes | 4 / 1 | 1 |
| [#57](https://github.com/dhirendrait1/crypto-intelligence-network/pull/57) | Integrate CIN source provenance with monitoring freshness | main | yes | 36 / 0 | 4 |
| [#58](https://github.com/dhirendrait1/crypto-intelligence-network/pull/58) | Enforce fail-closed source-specific freshness policy resolution | #57 | yes | 5 / 0 | none |
| [#59](https://github.com/dhirendrait1/crypto-intelligence-network/pull/59) | Build Stage 6 mobile-first CIN dashboard preview | main | no | 97 / 0 | 4 |
| [#60](https://github.com/dhirendrait1/crypto-intelligence-network/pull/60) | Add endpoint regressions for CIN freshness policy enforcement | #58 | yes | 1 / 0 | none |
| [#61](https://github.com/dhirendrait1/crypto-intelligence-network/pull/61) | Add concurrency regressions for CIN alert outbox claims | #16 | no | 5 / 2 | 1 |
| [#62](https://github.com/dhirendrait1/crypto-intelligence-network/pull/62) | Test CIN alert recovery after crash before send | #61 | no | 8 / 4 | none |
| [#63](https://github.com/dhirendrait1/crypto-intelligence-network/pull/63) | Track uncertain CIN alert delivery outcomes | #16 | no | 37 / 0 | 1 |
| [#64](https://github.com/dhirendrait1/crypto-intelligence-network/pull/64) | Add market overview freshness boundary regressions | main | no | 2 / 0 | 4 |
| [#65](https://github.com/dhirendrait1/crypto-intelligence-network/pull/65) | Add provider cache freshness boundary regressions | main | yes | 1 / 0 | 4 |
| [#66](https://github.com/dhirendrait1/crypto-intelligence-network/pull/66) | Expose row-level market-data provider provenance | main | yes | 154 / 0 | 4 |
| [#67](https://github.com/dhirendrait1/crypto-intelligence-network/pull/67) | Add persistent CIN forecast ledger | main | no | 79 / 0 | 4 |
| [#68](https://github.com/dhirendrait1/crypto-intelligence-network/pull/68) | Use CoinPaprika for CIN broad-universe screening | main | no | 16 / 0 | 4 |
| [#69](https://github.com/dhirendrait1/crypto-intelligence-network/pull/69) | Use Coinbase public data for CIN market-data endpoint | main | yes | 19 / 0 | 4 |
| [#70](https://github.com/dhirendrait1/crypto-intelligence-network/pull/70) | Add SQLite evidence persistence reliability tests | #66 | no | 192 / 0 | 4 |
| [#71](https://github.com/dhirendrait1/crypto-intelligence-network/pull/71) | Add gated read-only CIN Markets screen and frontend contracts | #70 | yes | 13 / 0 | 1 |
| [#72](https://github.com/dhirendrait1/crypto-intelligence-network/pull/72) | Add responsive read-only Markets candlestick visualization | #71 | yes | 4 / 0 | 1 |
| [#73](https://github.com/dhirendrait1/crypto-intelligence-network/pull/73) | Add source-derived Markets snapshot metrics | #72 | yes | 4 / 0 | 1 |
| [#74](https://github.com/dhirendrait1/crypto-intelligence-network/pull/74) | Add session market watchlist controls | #73 | yes | 5 / 0 | 1 |
| [#75](https://github.com/dhirendrait1/crypto-intelligence-network/pull/75) | Add synchronized relative market performance comparison | #74 | yes | 5 / 0 | 1 |
| [#76](https://github.com/dhirendrait1/crypto-intelligence-network/pull/76) | Add market data freshness and integrity monitoring | #75 | no | 6 / 0 | 1 |
| [#77](https://github.com/dhirendrait1/crypto-intelligence-network/pull/77) | Add session market data quality history | #76 | no | 8 / 0 | 1 |
| [#78](https://github.com/dhirendrait1/crypto-intelligence-network/pull/78) | Add feature-gated market integrity diagnostics | #77 | yes | 9 / 0 | 1 |
| [#79](https://github.com/dhirendrait1/crypto-intelligence-network/pull/79) | Lock Markets controls during active data requests | #78 | no | 12 / 0 | 1 |
| [#80](https://github.com/dhirendrait1/crypto-intelligence-network/pull/80) | Reject duplicate candle timestamps in Markets API contract | #79 | yes | 2 / 0 | 1 |
| [#81](https://github.com/dhirendrait1/crypto-intelligence-network/pull/81) | Validate candle UTC and epoch timestamp consistency | #80 | yes | 2 / 0 | 1 |
| [#82](https://github.com/dhirendrait1/crypto-intelligence-network/pull/82) | Reject candle rows outside the requested UTC window | #81 | yes | 2 / 0 | 1 |
| [#83](https://github.com/dhirendrait1/crypto-intelligence-network/pull/83) | Bind candle response window to the exact client request | #82 | yes | 2 / 0 | 1 |
| [#84](https://github.com/dhirendrait1/crypto-intelligence-network/pull/84) | Validate candle timestamps against interval boundaries | #83 | no | 3 / 0 | 1 |
| [#85](https://github.com/dhirendrait1/crypto-intelligence-network/pull/85) | Validate candle close-state metadata against retrieval time | #84 | no | 2 / 0 | 1 |
| [#86](https://github.com/dhirendrait1/crypto-intelligence-network/pull/86) | Report missing intervals in Markets candle diagnostics | #85 | yes | 3 / 0 | 1 |
| [#87](https://github.com/dhirendrait1/crypto-intelligence-network/pull/87) | Classify freshness and contract outcomes in market diagnostics | #86 | yes | 5 / 1 | none |
| [#88](https://github.com/dhirendrait1/crypto-intelligence-network/pull/88) | Report Coinbase provider row accounting without overstating coverage | #87 | no | 12 / 0 | 2 |
| [#89](https://github.com/dhirendrait1/crypto-intelligence-network/pull/89) | Expose Coinbase provider accounting in gated Markets diagnostics | #88 | no | 24 / 6 | 2 |
| [#90](https://github.com/dhirendrait1/crypto-intelligence-network/pull/90) | Validate requested-window candle bounds and interval ranges | #89 | yes | 2 / 0 | 1 |
| [#91](https://github.com/dhirendrait1/crypto-intelligence-network/pull/91) | Keep requested-window coverage unestablished when returned rows are in bounds | #90 | yes | 1 / 0 | 1 |
| [#92](https://github.com/dhirendrait1/crypto-intelligence-network/pull/92) | Test requested-window candle boundary edge cases | #91 | yes | 1 / 0 | 1 |
| [#93](https://github.com/dhirendrait1/crypto-intelligence-network/pull/93) | Test invalid requested-window timestamp handling | #92 | yes | 1 / 0 | 1 |
| [#94](https://github.com/dhirendrait1/crypto-intelligence-network/pull/94) | Preserve quote-asset identity in Coinbase fallback | #88 | yes | 4 / 0 | none |
| [#95](https://github.com/dhirendrait1/crypto-intelligence-network/pull/95) | Test USDT fallback isolation and provider provenance | #94 | yes | 2 / 0 | none |
| [#96](https://github.com/dhirendrait1/crypto-intelligence-network/pull/96) | Validate Coinbase fallback candle payload quality | #95 | yes | 3 / 0 | none |
| [#97](https://github.com/dhirendrait1/crypto-intelligence-network/pull/97) | Add cross-provider candle consistency diagnostics | #96 | yes | 6 / 0 | none |
| [#98](https://github.com/dhirendrait1/crypto-intelligence-network/pull/98) | Expose explicit public candle freshness status | #97 | yes | 3 / 0 | none |
| [#99](https://github.com/dhirendrait1/crypto-intelligence-network/pull/99) | Add bounded failover for transient public provider failures | #98 | yes | 3 / 0 | none |
| [#100](https://github.com/dhirendrait1/crypto-intelligence-network/pull/100) | Harden provider candle response integrity | #99 | yes | 3 / 0 | none |
| [#101](https://github.com/dhirendrait1/crypto-intelligence-network/pull/101) | Enforce candle timeframe timestamp consistency | #100 | yes | 3 / 0 | none |
| [#102](https://github.com/dhirendrait1/crypto-intelligence-network/pull/102) | Report missing intervals in public candle timelines | #101 | yes | 1 / 0 | none |
| [#103](https://github.com/dhirendrait1/crypto-intelligence-network/pull/103) | Validate public candle UTC timeframe boundaries | #102 | yes | 1 / 0 | none |
| [#104](https://github.com/dhirendrait1/crypto-intelligence-network/pull/104) | Respect provider-specific weekly candle boundaries | #103 | yes | 1 / 0 | none |
| [#105](https://github.com/dhirendrait1/crypto-intelligence-network/pull/105) | Use explicit provider identity for candle boundary validation | #104 | yes | 1 / 0 | none |
| [#106](https://github.com/dhirendrait1/crypto-intelligence-network/pull/106) | Count monthly provider comparison gaps by calendar boundaries | #105 | yes | 1 / 0 | none |
| [#107](https://github.com/dhirendrait1/crypto-intelligence-network/pull/107) | Unify candle timeline and provider comparison validation | #106 | yes | 1 / 0 | none |
| [#108](https://github.com/dhirendrait1/crypto-intelligence-network/pull/108) | Standardize safe market API integrity error responses | #107 | yes | 1 / 0 | none |
| [#109](https://github.com/dhirendrait1/crypto-intelligence-network/pull/109) | Fail closed on secondary provider rate limits | #108 | yes | 2 / 0 | none |
| [#110](https://github.com/dhirendrait1/crypto-intelligence-network/pull/110) | Reject future-open candles in freshness validation | #109 | yes | 2 / 0 | none |
| [#111](https://github.com/dhirendrait1/crypto-intelligence-network/pull/111) | Report requested versus returned candle coverage | #110 | yes | 1 / 0 | none |
| [#112](https://github.com/dhirendrait1/crypto-intelligence-network/pull/112) | Bound Coinbase candle pagination responses | #111 | yes | 1 / 0 | none |
| [#113](https://github.com/dhirendrait1/crypto-intelligence-network/pull/113) | Align Coinbase candle pagination windows | #112 | yes | 2 / 0 | none |
| [#114](https://github.com/dhirendrait1/crypto-intelligence-network/pull/114) | Reject ambiguous Kraken candle market responses | #113 | yes | 1 / 0 | none |
| [#115](https://github.com/dhirendrait1/crypto-intelligence-network/pull/115) | Verify Kraken candle market identity | #114 | yes | 2 / 0 | none |
| [#116](https://github.com/dhirendrait1/crypto-intelligence-network/pull/116) | Guard Kraken OHLC response cap and forming candle | #115 | yes | 1 / 0 | none |
| [#117](https://github.com/dhirendrait1/crypto-intelligence-network/pull/117) | Bound Binance candle requests to provider limit | #116 | yes | 1 / 0 | none |
| [#118](https://github.com/dhirendrait1/crypto-intelligence-network/pull/118) | Validate Coinbase rows before selecting latest candle window | #117 | yes | 1 / 0 | none |
| [#119](https://github.com/dhirendrait1/crypto-intelligence-network/pull/119) | Classify Kraken candle gaps without implying feed loss | #118 | yes | 1 / 0 | none |
| [#120](https://github.com/dhirendrait1/crypto-intelligence-network/pull/120) | Clarify Coinbase candle gaps and bound history rows | #119 | yes | 2 / 0 | none |
| [#121](https://github.com/dhirendrait1/crypto-intelligence-network/pull/121) | Reject conflicting Coinbase duplicate candle rows | #120 | yes | 4 / 0 | none |
| [#122](https://github.com/dhirendrait1/crypto-intelligence-network/pull/122) | Validate provider provenance in cross-provider candle comparisons | #121 | no | 3 / 0 | none |
| [#123](https://github.com/dhirendrait1/crypto-intelligence-network/pull/123) | Validate base and quote identity in provider comparisons | #122 | yes | 3 / 0 | none |
| [#124](https://github.com/dhirendrait1/crypto-intelligence-network/pull/124) | Add provider candle data-quality and freshness diagnostics | #123 | yes | 3 / 0 | none |
| [#125](https://github.com/dhirendrait1/crypto-intelligence-network/pull/125) | Fix out-of-order candle detection in data-quality audit | #124 | yes | 3 / 0 | none |
| [#126](https://github.com/dhirendrait1/crypto-intelligence-network/pull/126) | Reject mixed or inconsistent candle-provider provenance | #125 | yes | 3 / 0 | none |
| [#127](https://github.com/dhirendrait1/crypto-intelligence-network/pull/127) | Report provider candle coverage shortfalls explicitly | #126 | yes | 3 / 0 | none |
| [#128](https://github.com/dhirendrait1/crypto-intelligence-network/pull/128) | Audit leading and trailing historical candle-window coverage | #127 | yes | 4 / 0 | none |
| [#129](https://github.com/dhirendrait1/crypto-intelligence-network/pull/129) | Strengthen provider UTC candle-boundary regression coverage | #128 | yes | 2 / 0 | none |
| [#130](https://github.com/dhirendrait1/crypto-intelligence-network/pull/130) | Validate provider fallback and partial-response behavior | #129 | yes | 2 / 0 | none |
| [#131](https://github.com/dhirendrait1/crypto-intelligence-network/pull/131) | Reject malformed candle rows across public providers | #130 | yes | 5 / 0 | none |
| [#132](https://github.com/dhirendrait1/crypto-intelligence-network/pull/132) | Validate Coinbase pagination page boundaries | #131 | yes | 3 / 0 | none |
| [#133](https://github.com/dhirendrait1/crypto-intelligence-network/pull/133) | Validate Kraken response envelope and pagination cursor | #132 | yes | 3 / 0 | none |
| [#134](https://github.com/dhirendrait1/crypto-intelligence-network/pull/134) | Reject duplicate and out-of-order Kraken candles | #133 | yes | 3 / 0 | none |
| [#135](https://github.com/dhirendrait1/crypto-intelligence-network/pull/135) | Validate Kraken UTC candle interval boundaries | #134 | yes | 3 / 0 | none |
| [#136](https://github.com/dhirendrait1/crypto-intelligence-network/pull/136) | Classify malformed Kraken responses before provider fallback | #135 | yes | 3 / 0 | none |
| [#137](https://github.com/dhirendrait1/crypto-intelligence-network/pull/137) | Classify malformed Coinbase fallback responses as data-integrity failures | #136 | yes | 4 / 0 | none |
| [#138](https://github.com/dhirendrait1/crypto-intelligence-network/pull/138) | Gate cross-provider consistency on verified market identity | #137 | yes | 3 / 0 | none |
| [#139](https://github.com/dhirendrait1/crypto-intelligence-network/pull/139) | Report cross-provider historical window mismatches | #138 | yes | 3 / 0 | none |
| [#140](https://github.com/dhirendrait1/crypto-intelligence-network/pull/140) | Gate cross-provider candle value checks on verified volume units | #139 | yes | 3 / 0 | none |
| [#141](https://github.com/dhirendrait1/crypto-intelligence-network/pull/141) | Report cross-provider OHLC price-scale anomalies | #140 | yes | 4 / 0 | none |
| [#142](https://github.com/dhirendrait1/crypto-intelligence-network/pull/142) | Audit zero, missing, and abnormal candle volume | #141 | yes | 4 / 0 | none |
| [#143](https://github.com/dhirendrait1/crypto-intelligence-network/pull/143) | Add gated cross-provider volume discrepancy diagnostics | #142 | yes | 3 / 0 | none |
| [#144](https://github.com/dhirendrait1/crypto-intelligence-network/pull/144) | Record provider-specific candle volume semantics and provenance | #143 | yes | 3 / 0 | none |
| [#145](https://github.com/dhirendrait1/crypto-intelligence-network/pull/145) | Require source-verified semantics for cross-provider volume comparisons | #144 | yes | 4 / 0 | none |
| [#146](https://github.com/dhirendrait1/crypto-intelligence-network/pull/146) | Expose endpoint-specific evidence for provider candle volume units | #145 | yes | 3 / 0 | none |
| [#147](https://github.com/dhirendrait1/crypto-intelligence-network/pull/147) | Normalize explicit cross-provider market identity tokens safely | #146 | yes | 3 / 0 | none |
| [#148](https://github.com/dhirendrait1/crypto-intelligence-network/pull/148) | Centralize explicit quote-suffix parsing for provider fallbacks | #147 | yes | 3 / 0 | none |
| [#149](https://github.com/dhirendrait1/crypto-intelligence-network/pull/149) | Verify Coinbase fallback market identity against product catalogue | #148 | yes | 3 / 0 | none |
| [#150](https://github.com/dhirendrait1/crypto-intelligence-network/pull/150) | Verify Kraken AssetPairs base and quote identity fields | #149 | yes | 3 / 0 | none |
| [#151](https://github.com/dhirendrait1/crypto-intelligence-network/pull/151) | Validate Kraken AssetPairs spot asset classes | #150 | yes | 3 / 0 | none |
| [#152](https://github.com/dhirendrait1/crypto-intelligence-network/pull/152) | Validate Kraken AssetPairs market status before OHLC | #151 | yes | 5 / 0 | none |
| [#153](https://github.com/dhirendrait1/crypto-intelligence-network/pull/153) | Audit provider freshness threshold and stale snapshot handling | #152 | yes | 2 / 0 | none |
| [#154](https://github.com/dhirendrait1/crypto-intelligence-network/pull/154) | Classify provider failures and preserve fallback-chain provenance | #153 | yes | 4 / 0 | none |
| [#155](https://github.com/dhirendrait1/crypto-intelligence-network/pull/155) | Add severity classification to cross-provider data consistency | #154 | yes | 3 / 0 | none |
| [#156](https://github.com/dhirendrait1/crypto-intelligence-network/pull/156) | Add historical candle continuity and recovery integrity checks | #155 | yes | 4 / 0 | none |
| [#157](https://github.com/dhirendrait1/crypto-intelligence-network/pull/157) | Bound historical candle recovery pagination | #156 | yes | 3 / 0 | none |
| [#158](https://github.com/dhirendrait1/crypto-intelligence-network/pull/158) | Reject incomplete public market-data responses | #157 | yes | 5 / 0 | none |
| [#159](https://github.com/dhirendrait1/crypto-intelligence-network/pull/159) | Validate public provider JSON schema field types | #158 | yes | 3 / 0 | none |
| [#160](https://github.com/dhirendrait1/crypto-intelligence-network/pull/160) | Enforce provider timestamp units and UTC normalization | #159 | yes | 3 / 0 | none |
| [#161](https://github.com/dhirendrait1/crypto-intelligence-network/pull/161) | Normalize provider response ordering and duplicate records deterministically | #160 | yes | 4 / 0 | none |
| [#162](https://github.com/dhirendrait1/crypto-intelligence-network/pull/162) | Enforce canonical bounded provider snapshot integrity | #161 | yes | 3 / 0 | none |
| [#163](https://github.com/dhirendrait1/crypto-intelligence-network/pull/163) | Propagate provider freshness and stale-data warnings consistently | #162 | yes | 3 / 0 | none |
| [#164](https://github.com/dhirendrait1/crypto-intelligence-network/pull/164) | Use a consistent UTC retrieval clock across market-data responses | #163 | yes | 3 / 0 | none |
| [#165](https://github.com/dhirendrait1/crypto-intelligence-network/pull/165) | Expose structured provider fallback provenance | #164 | yes | 5 / 0 | none |
| [#166](https://github.com/dhirendrait1/crypto-intelligence-network/pull/166) | Make provider fallback eligibility explicit and regression-tested | #165 | yes | 2 / 0 | none |
| [#167](https://github.com/dhirendrait1/crypto-intelligence-network/pull/167) | Validate provider fallback response integrity | #166 | yes | 2 / 0 | none |
| [#168](https://github.com/dhirendrait1/crypto-intelligence-network/pull/168) | Enforce requested candle history-window boundaries | #167 | yes | 3 / 0 | none |
| [#169](https://github.com/dhirendrait1/crypto-intelligence-network/pull/169) | Validate Kraken OHLC pagination cursor integrity | #168 | yes | 3 / 0 | none |
| [#170](https://github.com/dhirendrait1/crypto-intelligence-network/pull/170) | Audit Coinbase multi-page candle boundary integrity | #169 | yes | 4 / 0 | none |
| [#171](https://github.com/dhirendrait1/crypto-intelligence-network/pull/171) | Validate Coinbase product availability and trading status | #170 | yes | 4 / 0 | none |
| [#172](https://github.com/dhirendrait1/crypto-intelligence-network/pull/172) | Validate Coinbase candle response ordering and chronology | #171 | yes | 5 / 0 | none |
| [#173](https://github.com/dhirendrait1/crypto-intelligence-network/pull/173) | Tighten Coinbase pagination boundary integrity | #172 | yes | 3 / 0 | none |
| [#174](https://github.com/dhirendrait1/crypto-intelligence-network/pull/174) | Audit Coinbase requested-window candle coverage | #173 | yes | 3 / 0 | none |
| [#175](https://github.com/dhirendrait1/crypto-intelligence-network/pull/175) | Validate Coinbase pagination page completeness | #174 | yes | 3 / 0 | none |
| [#176](https://github.com/dhirendrait1/crypto-intelligence-network/pull/176) | Reconcile Coinbase pagination timestamp windows | #175 | yes | 3 / 0 | none |
| [#177](https://github.com/dhirendrait1/crypto-intelligence-network/pull/177) | Validate Coinbase pagination failure and recovery behavior | #176 | yes | 2 / 0 | none |
| [#178](https://github.com/dhirendrait1/crypto-intelligence-network/pull/178) | Bound Coinbase response payload resource usage | #177 | yes | 3 / 0 | none |
| [#179](https://github.com/dhirendrait1/crypto-intelligence-network/pull/179) | Validate Coinbase product catalogue identity and ambiguity | #178 | yes | 2 / 0 | none |
| [#180](https://github.com/dhirendrait1/crypto-intelligence-network/pull/180) | Make Coinbase symbol-to-product mapping explicit | #179 | yes | 3 / 0 | none |
| [#181](https://github.com/dhirendrait1/crypto-intelligence-network/pull/181) | Test Coinbase candle request URL and query integrity | #180 | yes | 3 / 0 | none |
| [#182](https://github.com/dhirendrait1/crypto-intelligence-network/pull/182) | Audit Coinbase HTTP response status classification | #181 | yes | 3 / 0 | none |
| [#183](https://github.com/dhirendrait1/crypto-intelligence-network/pull/183) | Audit Coinbase transport timeout and connection failures | #182 | yes | 3 / 0 | none |
| [#184](https://github.com/dhirendrait1/crypto-intelligence-network/pull/184) | Audit Coinbase retry and repeated-request consistency | #183 | yes | 2 / 0 | none |
| [#185](https://github.com/dhirendrait1/crypto-intelligence-network/pull/185) | Audit Coinbase best-effort snapshot consistency | #184 | yes | 4 / 0 | none |
| [#186](https://github.com/dhirendrait1/crypto-intelligence-network/pull/186) | Audit Coinbase current candle finalization | #185 | yes | 3 / 0 | none |
| [#187](https://github.com/dhirendrait1/crypto-intelligence-network/pull/187) | Audit Coinbase OHLCV numeric integrity | #186 | yes | 3 / 0 | none |
| [#188](https://github.com/dhirendrait1/crypto-intelligence-network/pull/188) | Audit Coinbase candle interval alignment integrity | #187 | yes | 4 / 0 | none |
| [#189](https://github.com/dhirendrait1/crypto-intelligence-network/pull/189) | Audit Coinbase candle interval continuity and missing buckets | #188 | yes | 2 / 0 | none |
| [#190](https://github.com/dhirendrait1/crypto-intelligence-network/pull/190) | Enforce exact Coinbase candle row schema cardinality | #189 | yes | 3 / 0 | none |
| [#191](https://github.com/dhirendrait1/crypto-intelligence-network/pull/191) | Validate Coinbase candle field types and timestamp representation | #190 | yes | 3 / 0 | none |
| [#192](https://github.com/dhirendrait1/crypto-intelligence-network/pull/192) | Guard Coinbase OHLCV decimal normalization boundaries | #191 | yes | 3 / 0 | none |
| [#193](https://github.com/dhirendrait1/crypto-intelligence-network/pull/193) | Verify Coinbase decimal precision and canonical float consistency | #192 | yes | 2 / 0 | none |
| [#194](https://github.com/dhirendrait1/crypto-intelligence-network/pull/194) | Validate Coinbase OHLC relationships before float normalization | #193 | yes | 4 / 0 | none |
| [#195](https://github.com/dhirendrait1/crypto-intelligence-network/pull/195) | Validate Coinbase successful response-envelope integrity | #194 | yes | 3 / 0 | none |
| [#196](https://github.com/dhirendrait1/crypto-intelligence-network/pull/196) | Validate Coinbase endpoint-specific response contracts | #195 | yes | 3 / 0 | none |
| [#197](https://github.com/dhirendrait1/crypto-intelligence-network/pull/197) | Validate Coinbase product-catalogue required field types | #196 | yes | 3 / 0 | none |
| [#198](https://github.com/dhirendrait1/crypto-intelligence-network/pull/198) | Validate Coinbase product increment metadata | #197 | yes | 4 / 0 | none |
| [#199](https://github.com/dhirendrait1/crypto-intelligence-network/pull/199) | Validate Coinbase product minimum and maximum size metadata | #198 | yes | 4 / 0 | none |
| [#200](https://github.com/dhirendrait1/crypto-intelligence-network/pull/200) | Fix stale freshness test and document CIN delivery gates | main | yes | 2 / 0 | 4 |
| [#201](https://github.com/dhirendrait1/crypto-intelligence-network/pull/201) | CIN research shortlist: staging-gated Coinbase dashboard API and provider validation | main | yes | 44 / 0 | 6 |
| [#202](https://github.com/dhirendrait1/crypto-intelligence-network/pull/202) | CIN cinematic intelligence dashboard based on user video reference | #87 | yes | 7 / 0 | 1 |
