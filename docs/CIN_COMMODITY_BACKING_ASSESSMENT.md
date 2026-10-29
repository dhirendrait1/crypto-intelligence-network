# CIN Commodity-Backed Asset Evidence Assessment

## Purpose

The `commodity_backing_assessment.py` module provides a read-only evidence register for assets heuristically classified as commodity-backed. It is deliberately separate from the market-metric screening score.

## Evidence categories

- `reserve_attestation`: reserve report or attestation and its publication date.
- `redemption_terms`: eligibility, minimum redemption size, fees, jurisdiction limits, and process.
- `custody_or_issuer_disclosure`: issuer, custodian, legal structure, and relevant disclosures.

Each record stores evidence type, source name and URL, publication timestamp, checked timestamp, status, and notes. Accepted status values are `verified`, `unverified`, `stale`, and `unavailable`.

## Safety and interpretation

- The module validates metadata and freshness; it does **not** fetch or independently audit source documents.
- A supplied `verified` status is not a CIN certification. Missing metadata downgrades it to `unverified`.
- Evidence older than the configured freshness threshold (default 90 days) is marked `stale`.
- Missing evidence is unknown, not proof that backing exists or is absent.
- Complete evidence-category coverage means only that each category has a record marked verified; it is not a guarantee of reserves, solvency, custody, or redemption.\n- Coverage reports distinct URL hostnames as a source-diversity diagnostic. Multiple hostnames do **not** establish independent ownership, authorship, audit, or corroboration; CIN always reports `source_independence_verified: false`.
- Optional `source_role` values (`issuer`, `custodian`, `auditor`, `regulator`, `exchange`, `independent_research`, `other`) are caller-supplied classifications. Unknown or absent roles become `unspecified`; CIN reports role counts but always sets `source_role_authenticated: false` and `source_roles_authenticated: false.
- Conflicting statuses remain visible through per-status counts and a per-record conflict summary containing the supplied role, source name, URL, and status. Conflicts require manual review; CIN does not rank sources, select a winner, or authenticate source roles.
- Each normalized evidence record includes a deterministic SHA-256 fingerprint over its supplied evidence fields, source role, and notes. This is a metadata-change detection aid only; it is not a signature, trusted timestamp, document-content hash, or proof of source authenticity.
- Optional caller-supplied `evidence_id` values (1–128 characters) provide stable keys for `compare_evidence_snapshots(previous, current)`. The comparator reports added, removed, changed, and unchanged records; duplicate IDs are marked ambiguous and records without IDs are counted as untracked. It compares only the two snapshots supplied by the caller: it does not persist version history or authenticate IDs.

## Example

```python
from commodity_backing_assessment import assess_commodity_asset

assessment = assess_commodity_asset("PAXG", evidence_records)
```

## API endpoint\n\nThe read-only API router exposes `POST /commodity-backing-assessment`. Submit a JSON body containing `symbol`, an optional `evidence` array, and optional `max_age_days` (default 90; allowed range 0–3650). Each evidence record may include `evidence_type`, `source_name`, `source_url`, `published_at`, `checked_at`, `status`, and `notes`. The endpoint assesses caller-supplied metadata only: it does not fetch source documents, does not modify stored state, and does not certify reserves. Empty evidence returns an explicit unverified/incomplete assessment. The Render build script copies the router and assessment module into the FastAPI application and registers the router.
