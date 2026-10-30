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

## Independent backup and restore drill (staging only)

A D1 Time Travel window is useful for point-in-time recovery, but it is not an independent backup. Keep an encrypted export outside the Cloudflare account and verify that it can be restored into a separate, empty staging database.

### Preconditions

- Obtain explicit owner approval before creating either staging database or running remote commands.
- Use only non-production databases. Never point the restore drill at the production database.
- Use a controlled workstation with encrypted storage and restricted access. Do not commit SQL exports or copy them into public artifacts.
- Record the source database name, export timestamp (UTC), Wrangler version, and operator in a private change log. Do not record credentials.

### Export

Run from the repository root after staging resources have been approved and configured:

```sh
npx wrangler d1 export cin-forecast-ledger-staging --remote --output=cin-forecast-ledger-staging-backup.sql
```

Confirm the command exits successfully and that the output file exists and is non-empty. Move the export into approved encrypted backup storage. Calculate and record a SHA-256 checksum for the exact stored file; verify that checksum again before restore. Treat the export as sensitive data.

### Restore into a separate database

Create a second, empty staging database only after approval, for example `cin-forecast-ledger-restore-test`. Do not reuse the source database.

```sh
npx wrangler d1 execute cin-forecast-ledger-restore-test --remote --file=cin-forecast-ledger-staging-backup.sql
```

If the import fails, stop. Do not retry against the source database and do not run ad-hoc cleanup statements. Preserve the failure output for diagnosis without exposing secrets.

### Integrity checks

Run these read-only checks against both source and restored staging databases and compare the results:

```sql
SELECT 'forecasts' AS ledger, COUNT(*) AS row_count,
       COUNT(DISTINCT forecast_id) AS unique_ids
FROM cin_forecasts
UNION ALL
SELECT 'observations', COUNT(*), COUNT(DISTINCT observation_id)
FROM cin_forecast_observations
UNION ALL
SELECT 'evaluations', COUNT(*), COUNT(DISTINCT forecast_id)
FROM cin_forecast_evaluations;

SELECT COUNT(*) AS evaluations_without_forecast
FROM cin_forecast_evaluations e
LEFT JOIN cin_forecasts f ON f.forecast_id = e.forecast_id
WHERE f.forecast_id IS NULL;

SELECT COUNT(*) AS evaluations_without_observation
FROM cin_forecast_evaluations e
LEFT JOIN cin_forecast_observations o ON o.observation_id = e.observation_id
WHERE o.observation_id IS NULL;
```

Also compare deterministic ordered exports of the three tables (or canonical row digests produced by a reviewed local script) so equal row counts alone are not treated as proof of equal content. Validate representative forecast, observation, and evaluation payloads through the read-only Worker/API path pointed at the restore-test database.

### Acceptance criteria

- Export command succeeds; encrypted artifact checksum is recorded and reverified.
- Restore completes into a different empty staging database.
- Per-table row counts and unique-ID counts match.
- Both orphan checks return zero.
- Canonical row-content comparison matches for all three tables.
- Representative records can be read from the restored database.
- The drill record includes duration, export size, checksum, restore result, comparison result, and any limitations.

A failed or incomplete drill blocks enabling forecast writes. This runbook does not authorize creating resources, storing secrets, changing Render configuration, deploying, or touching production data.

