# CIN forecast ledger Worker

This Worker is a private service gateway for the CIN FastAPI forecast ledger. It exposes one POST endpoint, `/v1/ledger`, and a fixed operation allowlist. It does not expose SQL, D1 administration, trading, wallet, or funds operations.

## Local validation and deployment preparation

Prerequisites: Node.js/npm and Wrangler. Do not run resource-creation commands until the owner has explicitly approved creating a non-production Cloudflare D1 database and Worker.

1. Copy `wrangler.toml.example` to `wrangler.toml`.
2. Create a non-production D1 database only after approval:
   `npx wrangler d1 create cin-forecast-ledger-staging`
3. Replace the example database name and placeholder ID in `wrangler.toml` with the returned non-production values.
4. Apply the schema to that database:
   `npx wrangler d1 execute cin-forecast-ledger-staging --remote --file=worker/migrations/0001_forecast_ledger.sql`
5. Set a dedicated high-entropy Worker service credential using Wrangler's secret interface:
   `npx wrangler secret put CIN_FORECAST_WORKER_TOKEN`
6. Deploy only the staging Worker after approval:
   `npx wrangler deploy --config worker/wrangler.toml`

The same randomly generated service credential must then be stored as the Render environment variable `CIN_FORECAST_D1_WORKER_TOKEN`, with the Worker HTTPS origin in `CIN_FORECAST_D1_WORKER_URL`. Never use a Cloudflare account API token for this application-to-Worker authentication. Never commit secrets, generated credentials, real database IDs, or a populated `wrangler.toml`.

## Operations

- `create_forecast`
- `insert_observation`
- `get_forecast`
- `get_evaluation`
- `list_forecasts`
- `list_evaluations`
- `evaluate_forecast`

All values are passed as JSON and bound to prepared SQL statements. The Worker enforces bearer authentication and a 64 KiB request limit. The FastAPI API retains its separate `CIN_FORECAST_WRITE_TOKEN` authorization gate.

## Important limitations

- This first adapter is a development implementation, not production-certified.
- Run Worker-side integration tests against a staging D1 database before using it for real forecast records.
- D1 batch/transaction semantics, duplicate-ID races, concurrent evaluations, error mapping, pagination, and quota exhaustion need explicit integration coverage.
- A successful Worker deployment alone does not prove end-to-end durable persistence.
- Keep forecast writes disabled until staging tests and an independent export/restore check pass.
