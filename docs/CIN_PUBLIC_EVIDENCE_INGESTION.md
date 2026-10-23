# CIN Public Evidence Ingestion — Milestone 2

## Scope
The first connector is read-only and ETH-only. It retrieves a narrow set of public GitHub repository metadata for an allowlisted set of Ethereum repositories:
- `ethereum/go-ethereum`
- `ethereum/consensus-specs`
- `ethereum/ethereum-org-website`

Endpoint: `POST /public-evidence-ingestion`

Example request:
```json
{"symbol":"ETH","repository":"ethereum/go-ethereum"}
```

No API key is required. The connector uses Python's standard library, a bounded timeout, a response-size cap, an explicit User-Agent, and an allowlist. It does not download repository files, accept arbitrary URLs, access accounts, or perform transactions.

## Evidence semantics
The response keeps distinct:
- `retrieval_status`: whether the source response was obtained;
- `validation_status`: whether basic response shape was checked;
- `freshness_status`: deferred to a policy evaluator;
- `claim_verification_status`: remains `unverified`;
- `independently_verified`: always `false` for this connector.

GitHub repository metadata is a partial proxy for developer activity. It does not establish protocol adoption, project quality, security, token value, or investment merit. An HTTP 200 response is not claim verification.

## Operational constraints
- ₹0-first and public data only.
- No trade/order execution, wallet access, custody, or fund movement.
- Network calls must be mocked in unit tests.
- Render's build patch script must copy both new Python modules into `cin/app/` and register the router.
- Production deployment must be verified separately after CI passes.
