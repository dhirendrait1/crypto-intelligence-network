# CIN Growth Fundamentals Evidence Assessment

## Endpoint

`POST /growth-fundamentals-assessment`

Request fields:
- `symbol`: required asset ticker (1–20 characters).
- `evidence`: optional list (up to 200) of caller-supplied records.
- `max_age_days`: freshness threshold from 0 to 3650 days; defaults to 90.

Each record accepts `category`, optional caller-supplied `evidence_id` and `source_role`, `source_name`, `source_url`, `published_at`, `checked_at`, `status`, and optional `notes`. A `verified` record requires valid publication and check timestamps; future timestamps and a check time preceding publication downgrade it to unverified. Source roles are unauthenticated caller metadata. Each normalized record carries a metadata SHA-256 fingerprint; this is not a document hash, signature, or proof of authenticity.

The assessment remains metadata-only: CIN does not fetch or independently audit the cited material. The coverage score is not a quality score or investment recommendation.

## Coverage categories

- `usage_and_adoption`
- `fees_and_revenue`
- `token_utility`
- `tokenomics_and_unlocks`
- `security_and_audits`
- `developer_activity`
- `holder_concentration`
- `ecosystem_and_competition`

## Interpretation and limits

The coverage score is the percentage of categories with at least one supplied evidence record marked verified after basic metadata and freshness checks. It measures **evidence coverage only**, not coin quality, expected return, or investment suitability. The API does not fetch source documents or independently validate their claims. A complete evidence set is not a security audit or investment recommendation. Missing evidence remains unknown, not proof of quality or fraud.

CIN remains read-only: this endpoint does not place orders, connect wallets, or move funds.
