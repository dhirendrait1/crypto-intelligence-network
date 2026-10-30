# CIN Step 23 — Provider Governance and Source-of-Truth Integrity Readiness v1

**Status:** Repository-level readiness review; no provider configuration, live source selection, fallback, or production ingestion changed.
**Scope:** Public evidence connector and its mapping into CIN evidence semantics.
**Boundary:** Read-only intelligence only; no trading, wallet access, key handling, or fund movement.

## 1. Executive finding

The reviewed Step 23 connector is narrowly allowlisted to three public GitHub repositories, uses a fixed GitHub API root, validates selected response fields and timestamps, bounds timeout and response size, and marks retrieved metadata explicitly unverified. A separate pure mapper preserves that unverified state and creates only a context-only relationship.

This is a source-specific technical control, not a complete provider-governance framework. The reviewed path does not establish an approved source registry with owners and terms, metric-specific source-of-truth rules, independent corroboration requirements, provider health scoring, a governed fallback matrix, or conflict-resolution tolerances. GitHub repository metadata is not authoritative for broader ecosystem health, developer quality, adoption, or investment merit.

**Disposition:** Narrow technical allowlisting and provenance controls exist. Cross-provider governance and source-of-truth integrity remain open.

## 2. Existing controls observed

| Control | Repository evidence | Assessment |
|---|---|---|
| Source allowlist | Three fixed Ethereum-related GitHub repositories | Implemented for this connector only |
| Destination control | Fixed GitHub API root and allowlisted repository path | Reduces arbitrary destination exposure |
| Request bounds | Integer timeout 1–15 seconds; response cap 1 MB | Implemented |
| Response validation | Repository identity, default branch, timestamps, counters, archived flag | Implemented for selected fields |
| Freshness | pushed_at, fallback updated_at; 7-day threshold; future tolerance | Explicit but source-activity-specific |
| Provenance | Source URL, retrieval timestamp, provider timestamps, freshness state | Preserved in output |
| Verification semantics | unverified and independently_verified=false | Explicitly conservative |
| Evidence mapping | Pure mapper; canonical source URL; context-only relationship; not_assessed claim | Implemented, not API-wired |
| API storage boundary | Injected store remains unused; route is read-only | No API persistence |
| Client error handling | Stable generic 502 for provider exceptions | Avoids provider detail disclosure |

The 7-day GitHub activity threshold is not a universal freshness rule for market prices, reserves, news, on-chain metrics, or other evidence classes.

## 3. Provider governance contract required

Before adding a source or treating it as authoritative, maintain a versioned provider registry containing:

- Provider and source namespace; exact API/feed and permitted resource scope.
- Data owner/operator and accountable CIN reviewer.
- Public/private access tier, authentication requirements, terms, license, attribution and redistribution restrictions.
- Permitted collection purpose, rate limits, quotas, and retention constraints.
- Supported symbols/entities, metrics, units, quote currencies, chain/network, and geographic scope.
- Timestamp semantics: event time, publication time, provider update time, observation time, retrieval time.
- Known coverage gaps, revisions, methodology changes, and outage behavior.
- Validation rules, freshness budget, uncertainty labels, and source-specific fallback eligibility.
- Version/effective date, review date, and retirement/suspension criteria.

Unknown or unreviewed providers must remain disabled. Public accessibility alone does not establish permission to retain, redistribute, or use a source for every purpose.

## 4. Source-of-truth is metric-specific

Do not assign one universal best provider. Define source precedence separately for each metric and context. Comparison requires matching:

- Asset identity and canonical instrument/pair.
- Quote currency and conversion methodology.
- Venue, chain/network, contract address, and token denomination.
- Measurement interval, aggregation method, and timezone.
- Event-time versus retrieval-time semantics.
- Unit, decimal precision, and methodology version.

A provider can be authoritative for its own published metadata without being authoritative for a derived interpretation. Exchange prices are venue-specific observations, not automatically a universal market price. Repository stars, forks, or push time are not direct measures of developer quality or adoption. Reserve claims require issuer/custodian/auditor evidence and cannot be established by a token listing or market-data provider.

## 5. Fallback and substitution policy

A fallback is allowed only when a metric-specific policy explicitly approves the alternate source and comparability conditions are satisfied.

1. Preserve the primary-source failure status and timestamp.
2. Label the alternate source and provenance; never overwrite primary source identity.
3. Verify entity, unit, quote currency, interval, and timestamp compatibility.
4. Record that fallback was used and why; do not blend sources silently.
5. If comparability or policy is unknown, return unavailable/unknown rather than substitute.
6. Any future cache must carry original source, observation/retrieval times, cache age, and explicit stale status.
7. Do not retry indefinitely or fan out to every provider after a failure; obey provider request budgets and cooldowns.
8. A 429, timeout, malformed payload, or stale response is a failed/limited retrieval, not evidence that the underlying metric is zero.

The reviewed GitHub evidence route has no governed alternate source or provider fallback. No fallback is implemented by this review.

## 6. Conflict and source-disagreement handling

When sources disagree, preserve both observations and provenance. Before classifying a conflict, confirm they refer to the same entity, metric, unit, venue/scope, interval, and timestamp semantics.

A future metric-specific conflict policy should define normalization, conversion rules, acceptable time skew and tolerance, source independence, upstream dependencies, revision behavior, escalation thresholds, and human-review requirements.

Use explicit statuses such as consistent, conflicting, incomparable, stale, partial, unavailable, and unknown. Do not average conflicting values or choose the newest/highest-ranked provider without a documented method. Repeated copies of one upstream assertion are not independent corroboration. Contextual evidence must not be promoted to supports/contradicts or verified merely because multiple endpoints repeat it.

## 7. Data-quality and integrity acceptance tests

Before enabling any provider or fallback, require deterministic tests for:

- Wrong entity, pair, network, contract, quote currency, or unit.
- Missing, malformed, timezone-naive, future, stale, and out-of-order timestamps.
- Duplicate records, provider revisions, and changed values under stable IDs.
- Zero, negative, non-finite, extreme, and type-confused numeric values where applicable.
- Partial responses and unknown fields.
- HTTP 429, 5xx, timeout, DNS/TLS failure, oversized payload, malformed JSON.
- Provider failover with preserved source and stale/fallback labels.
- Conflict detection, incomparable observations, and no silent averaging.
- Provenance preservation through mapping, storage, API response, and display.
- Provider terms/retention constraints and explicit suspension behavior.

Mocked tests establish parser behavior, not live provider correctness or source authority. Live smoke tests require separate authorization and must be read-only.

## 8. Current gaps and decisions

| Gap | Current disposition |
|---|---|
| Versioned provider registry and accountable source owner | Not evidenced |
| Metric-specific source precedence and authority | Not established |
| Provider terms/license/retention review register | Not established by this code review |
| Fallback eligibility and comparability matrix | Not implemented |
| Universal freshness policy | Not appropriate; metric-specific policies required |
| Cross-provider conflict tolerance calibration | Outstanding elsewhere in roadmap |
| Independence/correlation of upstream sources | Not assessed |
| Provider health and quota monitoring | Not evidenced in this path |
| Live source validation | Not performed in this review |
| API persistence/mapping activation | Remains disabled and unwired |

## 9. Explicit non-actions

No provider was added, removed, or promoted. No source precedence, fallback, cache, retry, conflict tolerance, provider score, runtime registry, live request, persistence wiring, deployment, Render/Cloudflare setting, or paid service was changed. No source is certified authoritative by this document.

**Disposition:** Provider governance and source-of-truth integrity requirements are documented; implementation and live validation remain open. Step 23 remains Partial.
