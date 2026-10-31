# CIN F-23 — API Client and Shared Data-State Layer

**Date:** 2026-10-31  
**Status:** Initial implementation committed; frontend CI verification pending

## Delivered
- Added `frontend/src/lib/api.ts`: one fetch boundary, explicit environment-configured API origin (`VITE_CIN_API_BASE_URL`), request timeout, safe HTTP/network/timeout error normalization, and service health/readiness calls.
- Added `frontend/src/components/DataState.tsx`: shared presentation for fresh, stale, partial, conflicting, unavailable, unknown and error states, with source/retrieval metadata slots.
- Connected the app shell to `/health` and `/ready` only when an API origin is configured. No origin is hard-coded.
- Added unit coverage for no implicit production API origin and shared state/provenance presentation.

## Contract boundary
- The checked-in API source confirms `/market-data` and `/coin-screening` have provider-specific response semantics, but these endpoints currently use CoinGecko and/or CoinPaprika. They are deliberately not wired into the browser client because CIN's saved provider preference is Coinbase-first and CoinGecko is excluded unless that preference is explicitly changed.
- Market/assessment panels therefore remain visibly unconnected; the browser does not make live market requests or imply provider validation.
- The health/readiness response classifier only treats explicit `status: ok` or `status: ready` as healthy. Other shapes remain unknown/unavailable rather than being promoted to healthy.
- No shared API response envelope, cross-module conformance model, CORS change, backend route, scoring change, provider integration or persistence activation was introduced.

## Remaining acceptance
- GitHub Actions typecheck, unit tests and build must pass.
- Add a generated committed npm lockfile.
- Validate actual health/readiness response payloads against the deployed API before enabling a live origin.
- Add typed Coinbase-first market/assessment contracts only after the backend contract and provider policy align.
- Add robust stale/partial/conflict classification tests using representative backend fixtures.

No Render, Cloudflare, DNS or production deployment was changed. PR #70 remains open and unmerged.
