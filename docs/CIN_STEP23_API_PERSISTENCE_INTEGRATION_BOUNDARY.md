# CIN Step 23 — API/Persistence Integration Boundary

**Status:** Design boundary only; no runtime integration is enabled by this document.

## 1. Verified current behavior

- `cin_evidence_ingestion_api.py` exposes `POST /public-evidence-ingestion`.
- The route validates an ETH-only request and an allowlisted public GitHub repository, then returns the result of `fetch_github_repository_evidence()`.
- The route does not currently create a claim, write an evidence record, append an observation, or persist an assessment event.
- `EvidenceStore` in `cin_evidence_store.py` defines the append-oriented persistence contract.
- `LocalSQLiteEvidenceRepository` requires an explicitly supplied SQLite connection and caller-managed migration. It is documented as local/development-only and is not imported by the API.
- The SQLite adapter must not be treated as production storage on Render's ephemeral filesystem.

## 2. Proposed integration seam

The API layer should depend on the `EvidenceStore` protocol, not on `LocalSQLiteEvidenceRepository` or `sqlite3` directly.

A future integration should introduce an explicit application-level dependency/factory with these properties:

1. **Default disabled:** if no persistence adapter is configured, the endpoint retains its current read-only response behavior.
2. **Explicit opt-in:** persistence is enabled only by an explicit configuration and a constructed adapter supplied by the application.
3. **No hidden initialization:** importing the API module must not open a database, run migrations, create files, or select a backend.
4. **No implicit production SQLite:** the local SQLite adapter is available only to tests/local development; it is never automatically selected in Render.
5. **Clear failure semantics:** a persistence failure must not be reported as successful persistence. The API must return a controlled error or an explicit non-persisted result, according to a separately reviewed API contract.
6. **Provenance preserved:** retrieved provider metadata remains unverified evidence. Storage must not upgrade `claim_verification_status` or imply investment merit.
7. **Append-only history:** subsequent observations and assessments use append operations; no update/delete interface is introduced.
8. **No execution capability:** this boundary provides research evidence persistence only. It must not add order, wallet, key, or fund movement operations.

## 3. Required mapping before implementation

A future adapter-integration change must specify and test:

| API/source value | Persistence mapping |
|---|---|
| Allowlisted repository identity | `source_namespace` and `external_evidence_id` |
| GitHub metadata response | JSON `metadata` payload |
| Provider retrieval timestamp | `retrieved_at` and observation timestamp policy |
| Provider pushed/updated timestamp | `published_at` when valid |
| Retrieval status | `source_status` using an explicitly documented mapping |
| Claim builder output | `claim` input; initial status remains unverified/not assessed unless separately justified |
| Evidence-to-claim link | `relationship` input with an explicit review status |

Do not invent a quantitative ETH developer-activity claim from repository stars, forks, issues, or timestamps. Those fields are source metadata and only partial ecosystem indicators.

## 4. Acceptance gates for the next implementation change

- Unit tests prove the API works unchanged when no store is configured.
- Dependency tests prove the route uses the protocol and does not import or instantiate the SQLite adapter.
- Tests prove provider errors and persistence errors cannot be mislabeled as successful storage.
- Tests prove retrieved evidence is stored with provenance and remains unverified.
- Tests prove repeated retrieval appends an observation rather than overwriting history.
- A deployment review identifies a durable, free-tier-compatible storage option before any production persistence is enabled.
- No Render configuration, deployment, paid service, or production data migration is part of this design step.

## 5. Explicit non-goals

This document does not activate persistence, select a production database, change API responses, change Render, perform a deployment, or authorize merging PRs. It is an integration contract for a separately tested future change.
