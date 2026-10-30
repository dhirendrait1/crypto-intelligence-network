# CIN Forecast Storage Architecture Decision

Status: proposed architecture; no Cloudflare resources created and no production configuration changed.

## Decision

Use Cloudflare D1 as the durable forecast-ledger database, accessed by a narrowly scoped Cloudflare Worker API. The existing FastAPI service on Render Free remains the CIN application/API. FastAPI calls the Worker over HTTPS; the Worker uses its D1 binding.

Do not connect FastAPI directly to D1's administrative REST query endpoint for normal application traffic. Cloudflare documents that endpoint as best suited to administrative use and recommends a Worker proxy for applications outside Workers. A proxy also provides a place to enforce an allowlisted operation contract rather than accepting arbitrary SQL.

## Why this fits CIN

- D1 Free currently includes 5 GB total account storage, 5 million rows read/day, and 100,000 rows written/day.
- The current D1 Free per-database size limit is 500 MB; total account storage is 5 GB.
- Workers Free also has a shared 100,000 incoming Worker requests/day limit and 10 ms CPU time per request.
- Free-plan limits are hard stops: queries fail after daily read/write limits are reached, and writes/schema changes stop when storage is full until data is removed or the plan changes.
- D1 Free currently provides 7 days of Time Travel history. This is not a substitute for an independent export/backup policy.
- Render Free's local filesystem is ephemeral: SQLite data is lost on restart, redeploy, or spin-down. Render Free web services cannot attach persistent disks. Render Free Postgres expires after 30 days, so it is not a durable permanent-history solution.

## Proposed request path

1. CIN FastAPI validates the request model and existing CIN bearer authorization.
2. FastAPI sends a typed operation to a dedicated Worker endpoint over HTTPS, authenticated with a separate high-entropy service credential.
3. Worker verifies the service credential, validates operation-specific fields, and uses parameterized D1 prepared statements.
4. Worker returns a normalized result; FastAPI maps it to the existing forecast API response contract.
5. D1 is never exposed to browsers or unauthenticated callers. No Cloudflare account-wide API token is stored in Render.

## Worker API contract

Expose only the operations required by the current ledger:
- initialize/check schema through a controlled migration process (not an unauthenticated runtime endpoint);
- create forecast (idempotent ID; reject conflicting reuse);
- insert observation (idempotent ID; reject conflicting reuse);
- get/list forecasts;
- get/list evaluations;
- evaluate a forecast using a bounded nearest post-target observation;
- retrieve grouped scorecards.

Do not expose a generic SQL endpoint, arbitrary table names, schema mutation, D1 administration, or any trading, wallet, key, or funds operation.

Use parameterized SQL for every value. Enforce payload size and list limits at the Worker boundary. Keep writes disabled until both sides' credentials and the database have been configured and tested.

## Transaction and concurrency requirements

- Use D1 batch for logically atomic multi-statement operations; Cloudflare documents batch execution as sequential and transactional, rolling back the sequence if a statement fails.
- Preserve the current ledger's idempotency and immutable source-observation rules.
- Evaluation must be atomic: only one durable evaluation per forecast, with the chosen observation ID recorded.
- Add explicit conflict handling for duplicate IDs and concurrent evaluations.
- Do not assume SQLite-specific SQL, locking, or transaction behavior is portable. The D1 adapter must implement and test the same externally observable invariants using D1-supported SQL and batch semantics.

## Migration plan (not yet authorized or executed)

1. Add a storage interface to the FastAPI ledger layer and keep SQLite as an offline/local test adapter only.
2. Implement a D1 Worker with a fixed operation allowlist and parameterized SQL.
3. Add a FastAPI HTTP adapter configured only by CIN_FORECAST_D1_WORKER_URL and CIN_FORECAST_D1_WORKER_TOKEN; never place Cloudflare account API tokens in Render.
4. Add offline contract tests with a fake Worker transport, plus Worker-side tests for authorization, validation, idempotency, atomic evaluation, pagination, and failure handling.
5. Create a separate non-production D1 database and Worker only after explicit account-side approval. Validate persistence across Worker and Render restarts, quota exhaustion behavior, and export/restore.
6. Keep forecast write endpoints fail-closed until the storage adapter, secrets, and live persistence tests pass.

## $0 and account requirements

Cloudflare's current Workers product page advertises starting on the Free plan with no credit card required. D1 is included in Workers Free. The published limits are 5 million rows read/day, 100,000 rows written/day, 5 GB total account storage, and 500 MB per database; the Worker itself is limited to 100,000 requests/day and 10 ms CPU per request. Cloudflare states that D1 queries fail when daily read/write quotas are exceeded, and writes/schema changes stop when storage is full. These limits reset or require cleanup; they do not justify enabling a paid plan. CIN must remain on Free and must not add a payment method or upgrade to a paid plan.

## Current implementation gaps (must close before staging)

- The current Worker is an initial development adapter. It has an operation allowlist and prepared statements, but its read-then-write paths are not yet covered by real D1 concurrency tests.
- D1 `batch()` transaction semantics have not yet been implemented or verified for multi-statement ledger operations.
- List endpoints enforce a maximum row limit but do not yet provide cursor pagination.
- Worker-side tests cover authentication, path/method restrictions, operation allowlisting, payload size, malformed payload/limit rejection, and a Node SQLite compatibility harness for forecast/observation CRUD, idempotency, nearest-observation evaluation, and readback. This is a local SQL compatibility test, not a real Cloudflare D1 integration test.
- Error mapping, quota exhaustion, export/restore, and persistence across Worker/Render restarts remain unverified.

## Explicit non-actions

- No D1 database or Worker has been created.
- No Cloudflare token or secret has been requested, generated, stored, or exposed.
- No Render environment variables, database, disk, service settings, deployment, or production data have been changed.
- No PR has been merged.
- No forecast write endpoint is enabled in production.

## Official references

- D1 pricing: https://developers.cloudflare.com/d1/platform/pricing/
- D1 limits: https://developers.cloudflare.com/d1/platform/limits/
- D1 query API: https://developers.cloudflare.com/api/resources/d1/subresources/database/methods/query/
- Cloudflare guidance for external applications: https://developers.cloudflare.com/d1/tutorials/build-an-api-to-access-d1/
- D1 Worker bindings and batch semantics: https://developers.cloudflare.com/d1/worker-api/d1-database/
- Render Free limitations and ephemeral filesystem: https://render.com/docs/free
