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

The module is not yet connected to the live `/coin-screening` response. That integration should be a separate step with its own endpoint and tests.
