# CIN Step 23 — Public Endpoint Abuse and Rate-Limit Readiness v1

**Status:** Repository-level threat/readiness review only. No rate limiter, middleware, edge rule, deployment setting, or provider integration is activated by this document.  
**Scope:** Public evidence-ingestion HTTP endpoint and its outbound public GitHub metadata request.  
**Boundary:** The endpoint remains read-only; no evidence persistence, trading, wallet, key, or fund-movement capability is introduced.

## 1. Executive finding

The inspected evidence-ingestion route validates the ETH symbol and an exact repository allowlist before making a provider request. The connector uses a fixed GitHub API root, a bounded timeout (default 8 seconds; accepted integer range 1–15), and a maximum provider response read of 1,000,001 bytes to detect responses exceeding its 1,000,000-byte limit. These are useful input, destination, time, and response-size controls.

The reviewed route and connector do not show a per-caller request quota, concurrency limit, cooldown, abuse-detection policy, or explicit rate-limit response contract. No rate-limit middleware or edge policy was established by the repository evidence reviewed for this increment. This is a bounded review finding, not proof that an external hosting platform or network layer has no controls.

**Disposition:** Request/provider resource bounds are partially implemented; caller-level abuse controls and deployment-level rate-limit evidence remain unverified.

## 2. Observed controls and gaps

| Area | Repository evidence | Assessment |
|---|---|---|
| Request shape | Pydantic model forbids extra fields and bounds symbol/repository syntax | Implemented in route |
| Source destination | Exact repository allowlist; fixed GitHub API root; no arbitrary URL input | Implemented in connector |
| HTTP method | Provider request is GET | Read-only provider interaction |
| Outbound timeout | Default 8 seconds; bounded integer range 1–15 | Implemented |
| Provider response size | 1,000,000-byte maximum, with one extra byte read to detect overflow | Implemented |
| Caller quota | No per-principal/IP/client quota visible in reviewed route/connector | Not evidenced |
| Concurrency/backpressure | No route-level semaphore or queue bound visible in reviewed files | Not evidenced |
| Cooldown/retry policy | No caller cooldown or explicit retry-after policy visible | Not evidenced |
| Abuse telemetry | No rate-limit event/audit contract visible | Not evidenced |
| Edge/host controls | Render manifest describes service/build/start and autoDeploy; it does not document a rate-limit policy | Not established by repository manifest |
| Provider quota handling | Connector handles HTTP/network failures as source errors; no explicit 429-specific retry/backoff policy is visible | Incomplete |

## 3. Threats and failure modes

1. **Request flooding:** repeated valid requests can cause repeated outbound GitHub API calls even though the endpoint is read-only.
2. **Concurrency amplification:** many simultaneous requests can consume application workers and outbound sockets while each waits up to the configured timeout.
3. **Provider quota exhaustion:** repeated requests may encounter provider throttling; uncontrolled retries could amplify load.
4. **Availability degradation:** a slow provider can occupy request capacity until timeout.
5. **Cost/plan pressure:** read-only does not mean resource-free; abusive traffic can consume free-tier compute/network capacity or trigger provider limits.
6. **False confidence:** input allowlisting and response-size limits do not replace caller throttling or edge protection.

No evidence was found that this endpoint can execute trades, access wallets, use private keys, or move funds.

## 4. Minimum future control contract

Before broad public exposure or adding more source connectors, a separately reviewed implementation should define:

- A documented request budget per client/principal and a separate global service budget.
- A concurrency ceiling and bounded queue/backpressure behavior.
- A provider-specific outbound request budget that is stricter than the upstream quota.
- A short, bounded cooldown after repeated failures or 429 responses; no unbounded automatic retries.
- Stable HTTP 429 responses with a documented retry policy; do not disclose internal counters or provider credentials.
- Request correlation identifiers and payload-minimized counters for accepted, throttled, timed-out, provider-429, and provider-failure outcomes.
- Monitoring thresholds and a fail-safe behavior when the limiter state is unavailable.
- Explicit handling for shared/NAT IPs so legitimate users are not indiscriminately blocked.
- Tests for concurrent requests, quota boundary, reset windows, clock edge cases, provider 429, limiter outage, and absence of retry amplification.

A future implementation should prefer a low-cost, operationally supportable control compatible with CIN's $0-first constraint. Do not select a vendor or assume a free tier is sufficient until its current limits and deployment topology are verified.

## 5. Safe implementation sequence

1. Inventory the actual deployed route exposure, worker count, reverse proxy/edge path, and existing host-level controls without changing them.
2. Choose the rate-limit identity key and policy (authenticated principal if later introduced; otherwise a carefully reviewed network/client strategy).
3. Set conservative global, per-client, concurrency, and provider budgets from measured usage and provider terms.
4. Implement bounded middleware or edge controls with explicit 429 semantics and fail-closed/fail-safe behavior.
5. Add deterministic unit and HTTP integration tests, including concurrent and provider-throttle cases.
6. Verify behavior in a non-production environment before any separately approved deployment.

## 6. Acceptance gates

- Invalid and non-allowlisted requests do not reach the provider.
- Valid requests are bounded by per-client and global budgets.
- Concurrent requests cannot exceed the configured in-flight limit.
- Provider 429 and timeout responses do not trigger unbounded retries.
- Rate-limiter failure follows the documented safe policy.
- Throttling responses reveal no secrets, internal infrastructure, or sensitive policy data.
- Tests prove normal users can recover after the documented cooldown.
- Operational dashboards/logs record aggregate counters without raw payloads or credentials.
- No paid dependency or deployment change is introduced without explicit review and approval.

## 7. Explicit non-actions and unresolved items

No runtime code, middleware, rate-limit package, edge rule, Render configuration, Cloudflare configuration, provider quota, deployment, or API response contract was changed. The current public route remains read-only and persistence remains unwired.

Unresolved: actual deployed topology and traffic, hosting-level controls, appropriate quota values, client identity strategy, provider-specific 429 behavior, and the selected $0-compatible limiter implementation.

**Disposition:** Design/readiness review complete; caller-level and deployment-level abuse controls remain open. Step 23 remains Partial.
