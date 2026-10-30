# CIN Step 23 — GitHub Evidence Mapping v1

**Status:** Mapping specification only. No API writes or persistence activation.

## 1. Source contract

The current connector retrieves one allowlisted GitHub repository metadata snapshot. Its output contains:
- source identity and URL;
- repository name;
- retrieval and provider timestamps;
- a metadata value object (default branch, pushed/updated timestamps, stars, forks, open issues, archived);
- retrieval, shape-validation and freshness statuses;
- explicit limitations and an unverified claim-verification status.

These fields describe a public provider response. They do not establish ecosystem health, developer quality, adoption, security, token value, or investment merit.

## 2. Proposed initial evidence bundle mapping

| EvidenceStore field | Mapping | Rule |
|---|---|---|
| `source_namespace` | `github_public_repository_api` | Fixed provider namespace, not user input |
| `external_evidence_id` | `repository` | Canonical owner/repository identity |
| `evidence_type` | `public_repository_metadata_snapshot` | Fixed type |
| `metadata` | Complete normalized connector payload | Preserve provenance, limitations, missing fields and freshness; do not discard provider context |
| `observed_at` | `retrieved_at` | The system observed the response at retrieval time |
| `retrieved_at` | `retrieved_at` | Same source timestamp |
| `published_at` | `published_at` when it is a valid timezone-aware timestamp | Provider activity timestamp; do not call it publication of a claim |
| `checked_at` | Omitted | No independent check occurred |
| `source_status` | `cin_retrieved` only when retrieval_status is success; otherwise `unavailable`/ `invalid` under a separately specified error path | Do not persist failed retrieval as a successful bundle |

## 3. Claim and relationship semantics

The bundle requires a claim and relationship, but a repository metadata snapshot must not be turned into an ETH-market or investment claim.

If a future implementation uses this schema, the only acceptable initial claim is a narrow provenance claim, such as:

- subject: canonical repository identity;
- predicate: `public_metadata_snapshot_retrieved`;
- statement: `A public GitHub metadata snapshot was retrieved for {repository} at {retrieved_at}.`;
- value: source name, source URL, retrieval timestamp and validation/freshness labels;
- status: `not_assessed`;
- identifier method: versioned deterministic method documented in code.

The evidence relationship must be `context_only`, with review status `automated_candidate` and a rationale explicitly stating that the metadata is contextual source material, not proof of ecosystem development quality or investment merit.

Do not use `supports` for a claim about ETH adoption, network health, token valuation, project quality, or developer activity based solely on stars, forks, open issues, or timestamps.

## 4. Critical repeat-ingestion blocker

The current `EvidenceStore` protocol has append methods but no lookup method for resolving an existing evidence record by `source_namespace` and `external_evidence_id`.

The SQLite schema has a unique partial index on that pair. Calling `store_bundle` again for the same repository therefore cannot safely create another record; it will conflict. A correct repeat-ingestion flow must first resolve the existing `cin_evidence_id`, then call `append_observation`. It must never overwrite the earlier observation.

Before API persistence is implemented, the storage contract needs a reviewed identity-resolution method (or a separate repository query interface), plus tests for:
- first retrieval creates one record and one observation;
- repeated retrieval appends one observation to that same record;
- concurrent duplicate first-ingestion attempts are handled deterministically;
- provider failures create no successful evidence bundle;
- persistence failures are not reported as successful persistence.

## 5. Safety and rollout boundary

- No production storage backend is selected by this specification.
- Local SQLite remains a development/test adapter only.
- No automatic database initialization or migration.
- No Render or Cloudflare changes, deployment, paid service, or production data migration.
- No trading, order execution, wallet, key, or fund-movement capability.
- All retrieved metadata remains unverified source evidence.
