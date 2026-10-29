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
- Complete evidence-category coverage means only that each category has a record marked verified; it is not a guarantee of reserves, solvency, custody, or redemption.

## Example

```python
from commodity_backing_assessment import assess_commodity_asset

assessment = assess_commodity_asset("PAXG", evidence_records)
```

## API endpoint\n\nThe read-only API router exposes `POST /commodity-backing-assessment`. Submit a JSON body containing `symbol`, an optional `evidence` array, and optional `max_age_days` (default 90; allowed range 0–3650). Each evidence record may include `evidence_type`, `source_name`, `source_url`, `published_at`, `checked_at`, `status`, and `notes`. The endpoint assesses caller-supplied metadata only: it does not fetch source documents, does not modify stored state, and does not certify reserves. Empty evidence returns an explicit unverified/incomplete assessment. The Render build script copies the router and assessment module into the FastAPI application and registers the router.
