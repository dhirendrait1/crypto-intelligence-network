# CIN Step 23 — Disaster Recovery and Service Continuity Readiness v1

**Status:** Architecture/readiness review only. No production recovery automation, failover, deployment, or persistence activation.
**Scope:** Service availability and continuity for the current read-only API and future evidence-storage capability.
**Boundary:** No trade execution, wallet/key control, fund movement, or automatic write path.

## 1. Executive finding

The repository defines a Render Free web service manifest and CI workflows that validate a scaffold build, routes, offline tests, and local SQLite persistence boundaries. The manifest uses a single web service with automatic deployment enabled. Repository evidence does not establish a second serving region, warm standby, automated failover, measured recovery objectives, a tested rollback procedure, or a service-continuity exercise.

The existing backup/restore readiness document covers data-copy lineage, expiry, erasure replay, and restore quarantine. This document addresses a separate concern: keeping the service safe during dependency failures, platform outages, bad releases, overload, and partial recovery.

**Disposition:** Basic build/test validation exists, but no disaster-recovery or continuity capability is demonstrated. No recovery-time objective (RTO) or recovery-point objective (RPO) is set because service criticality, durable production data, and user expectations have not been approved.

## 2. Current architecture evidence and limits

| Area | Repository evidence | Continuity implication |
|---|---|---|
| Web service | Render manifest declares one Free web service, cin-api | Single declared serving service; no HA topology evidenced |
| Deployment | autoDeploy: true in manifest | Release can follow repository changes; no release approval gate evidenced in this manifest |
| Build | Extracts scaffold, applies patch, installs requirements | Build failure should prevent a new release; rollback procedure not evidenced here |
| CI | Offline tests and route registration assertions | Useful pre-release checks; not live failover or recovery tests |
| Health/readiness | CI asserts /health and /ready are registered | Registration alone does not prove dependency-aware readiness |
| External provider | Public GitHub metadata connector with bounded timeout and response size | Provider outage should degrade freshness, not create unsupported claims |
| Persistence | Local SQLite reference adapter only; not wired to API | No production data RPO can be claimed |
| Backups/failover | Separate readiness review documents missing operational inventory | No tested service/data failover evidenced |

The Render manifest is repository configuration evidence, not a live account inspection. It does not prove the current service runtime state, platform recovery guarantees, or provider-managed backup behavior.

## 3. Service continuity principles

1. **Read-only safety first:** if a provider is unavailable, return a controlled unavailable/stale/unknown state; never invent replacement data.
2. **No false readiness:** distinguish process liveness from readiness to serve a specific dependency-backed function.
3. **Bounded failure:** apply timeouts, response-size limits, concurrency budgets, and bounded retries; avoid retry storms.
4. **Degrade by capability:** preserve independent read-only routes where safe; isolate failed provider-dependent routes.
5. **No silent stale data:** every cached or fallback value must expose source, observation/retrieval time, freshness state, and fallback provenance.
6. **Fail closed for writes:** if future persistence authorization, schema, policy, or integrity checks are unavailable, reject writes.
7. **Recover in stages:** validate code, dependencies, data integrity, policy/erasure state, and monitoring before restoring public traffic.
8. **No automatic trade action:** outages and recovery must never trigger order placement or portfolio actions.

## 4. Failure-mode and safe-degradation matrix

| Failure scenario | Detection evidence required | Safe behavior | Recovery gate |
|---|---|---|---|
| Render/platform outage | Independent external availability check and provider status | API unavailable; do not claim data is current | Platform recovery plus health/readiness validation |
| Bad application release | Failed smoke tests, elevated 5xx, route/schema regression | Stop rollout or revert using approved procedure | Offline suite plus non-production smoke test |
| GitHub API outage/429 | Provider status class, timeout/429 counter | Mark provider result unavailable; bounded retry only | Provider healthy and bounded request probe succeeds |
| Market-data provider outage | Per-provider freshness/error state | Mark affected symbols/timeframes unavailable or stale; no silent substitution | Provider-specific validation and provenance check |
| News feed outage | Feed-specific retrieval status and age | Retain timestamped prior items only within approved freshness policy; otherwise unavailable | Feed recovers and timestamps/schema validate |
| DNS/TLS/network failure | Connection/DNS/TLS error class without secret logging | Fail affected outbound request quickly; no arbitrary alternate destination | Connectivity and certificate validation |
| Rate limiting/overload | 429/503, queue depth, in-flight saturation | Return bounded retry guidance; shed optional work; avoid retry amplification | Load returns below approved threshold |
| Dependency/package failure | Build lock/installation and import checks | Block release; retain known-good service if host supports it | Reproducible build and tests |
| Database unavailable (future only) | Connection and transaction health | Read-only degraded mode only if integrity/freshness is provable; otherwise disable dependent routes and reject writes | Restore/consistency checks and explicit release |
| Corrupt or partial restore (future only) | Integrity, migration, foreign-key, tombstone replay, residual scan | Quarantine; keep non-queryable | All restore acceptance gates pass |
| Secrets/credential suspected exposed | Secret scanning, access review, incident evidence | Disable affected integration using approved containment; rotate through credential owner | Credential rotation and access review |
| CI/GitHub outage | Workflow status unavailable | Missing CI evidence is not success; pause merge/release decisions | CI evidence restored and required checks green |

## 5. Recovery objectives and service tiers

Do not invent numeric RTO/RPO targets. Before production persistence or any availability promise, approve a service tier for each capability:

- **Tier 0 — Public read-only API shell:** acceptable outage window, user-facing status, and recovery owner.
- **Tier 1 — Provider-backed intelligence:** maximum tolerated staleness by provider and endpoint; source-specific fallback policy.
- **Tier 2 — Persisted evidence history (future):** approved RPO, RTO, backup frequency, restore validation, and erasure replay requirements.
- **Tier 3 — Administrative/privileged operations (future):** stronger identity, approval, audit, and recovery controls; disabled until implemented and approved.

For each tier, record business impact, maximum tolerable downtime, maximum tolerable data loss, RTO, RPO, dependency owner, test frequency, and approval. RPO is not applicable to the current unpersisted provider reads in the same way as a durable evidence database; do not imply zero data loss.

## 6. Recovery runbook sequence

1. Declare incident severity and record start time, affected capabilities, and incident owner.
2. Identify whether failure is platform, release, network, provider, application, or data-integrity related.
3. Contain using an approved reversible action; do not make unreviewed DNS, Render, Cloudflare, or secret changes.
4. Preserve sanitized logs and CI/deployment references; do not capture payloads or credentials.
5. For a bad release, use the documented host-supported rollback to a known-good immutable commit/artifact only after confirming provenance. If rollback capability is unavailable, keep the affected capability disabled rather than improvising.
6. Validate /health liveness separately from /ready readiness and perform route-level smoke checks for unaffected functions.
7. Validate each provider independently: destination allowlist, TLS, response shape, timestamp/freshness, size, and timeout.
8. If future persistent data is involved, follow the separate backup/restore gate: quarantine, integrity checks, migration compatibility, erasure replay, residual scan, and explicit release.
9. Re-enable capabilities incrementally and observe error, latency, and freshness indicators.
10. Close only after impact, data integrity, unresolved stale data, and corrective actions are documented.

## 7. Required continuity tests before activation

- Simulate provider timeout, 429, malformed response, stale response, and recovery; verify safe unavailable/stale states.
- Simulate one provider failure while independent routes remain usable.
- Verify no unbounded retries or request pile-up under overload.
- Exercise health versus readiness semantics for process alive/provider unavailable and process unavailable.
- Build a release candidate, run offline suite, and test rollback to a known-good immutable artifact in a non-production environment.
- Verify auto-deploy/approval behavior against actual hosting configuration before production release.
- If persistence is later enabled, test database loss, backup restore, RPO measurement, migration compatibility, erasure replay, quarantine, and RTO measurement.
- Run a tabletop incident exercise covering platform outage, provider outage, bad release, suspected credential exposure, and partial restore.
- Record test date, environment, injected failure, observed recovery time, data loss/staleness, operator, evidence, and corrective actions.

## 8. Decisions and evidence still required

- Approved service criticality and per-capability RTO/RPO.
- Actual Render service topology, region, platform status/guarantees, rollback support, and current auto-deploy behavior.
- Independent external availability monitor and owner.
- Provider-specific freshness budgets and fallback eligibility.
- Health/readiness semantics and route-level smoke-test ownership.
- Incident severity, escalation contact, and recovery authority.
- Durable production storage choice and backup/restore evidence before persistence.
- Whether release approval must replace or constrain current auto-deploy behavior; no change made here.

## 9. Explicit non-actions

No RTO/RPO values were invented. No second service, standby, failover, monitor, alert, retry loop, cache, database, backup, recovery automation, release gate, Render/Cloudflare setting, DNS change, or deployment was created or changed. No production persistence was enabled. This document does not claim any platform guarantee or successful disaster-recovery test.

**Disposition:** Service-continuity requirements and failure scenarios are documented; operational recovery remains unimplemented and unverified. Step 23 remains Partial.
