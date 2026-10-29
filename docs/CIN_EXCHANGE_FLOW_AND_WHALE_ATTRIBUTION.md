# CIN Exchange-Flow and Whale-Attribution Methodology

## Status and purpose

This is a read-only methodology specification for exchange-flow research. It does not implement a chain indexer, address label database, wallet connector, or fund movement capability. No wallet is controlled and no transaction is created, signed, routed, or executed.

The key distinction is:

- **Observed transfer:** a transaction/event recorded on a specified blockchain.
- **Exchange-associated flow:** an observed transfer involving an address that has sufficiently supported exchange attribution.
- **Entity attribution:** a claim that an address belongs to a named exchange, custodian, person, fund, or other entity.
- **Whale claim:** a claim about a large holder or coordinated actor. A large transfer alone does not establish a whale, beneficial owner, intent, or market impact.

CIN must not collapse these categories.

## 1. Minimum evidence required

Every flow observation must preserve:

- Chain/network identifier and asset contract or native-asset identifier.
- Transaction hash, event/log index where applicable, and block number.
- Block timestamp and CIN retrieval timestamp, both timezone-aware.
- From/to address in normalized chain-specific form.
- Raw integer amount, token decimals, and normalized amount; never infer decimals when metadata is missing.
- Event type (native transfer, token transfer, bridge, internal trace, exchange deposit/withdrawal, mint/burn) and the method used to identify it.
- Source/provider, endpoint or dataset, retrieval status, and source record URL/reference where available.
- Confirmation/finality status and reorg handling policy.
- Address-label evidence reference, observation date, label scope, confidence tier, and known limitations.

A transaction hash is an identifier for a chain observation, not proof of the real-world identity of either address.

## 2. Exchange address attribution tiers

Use explicit tiers; never silently promote an address.

- **Tier A — first-party confirmed:** exchange-published deposit/withdrawal address or official documentation with a verifiable chain/address mapping. Record exact source and validity period.
- **Tier B — reputable independently documented label:** attribution published by a named analytics provider or credible research source. Record provider, evidence URL, retrieval date, and whether the methodology is disclosed.
- **Tier C — community/heuristic label:** explorer tags, community lists, behavioral clustering, or unverified third-party claims. Treat as provisional and exclude from high-confidence aggregate exchange flow.
- **Unknown:** no adequate evidence. Do not assign an exchange identity.

Labels are time-bounded and chain-specific. An exchange label on one chain does not establish ownership of a same-looking address on another chain. Labels may become stale, be reused, or represent a custodian, hot-wallet operator, bridge, or service provider rather than the exchange itself.

CIN must retain the original source attribution and any conflicting labels. It must not select a preferred label automatically when evidence conflicts; return `manual_review_required`.

## 3. Flow definitions and calculation rules

For a fixed chain, asset, exchange-label set, and UTC observation window:

- **Observed deposits:** transfers from non-exchange-attributed addresses to addresses attributed to the exchange, subject to the selected attribution tier.
- **Observed withdrawals:** transfers from exchange-attributed addresses to non-exchange-attributed addresses.
- **Gross observed inflow:** sum of eligible observed deposits.
- **Gross observed outflow:** sum of eligible observed withdrawals.
- **Net observed flow:** gross observed inflow minus gross observed outflow.

All values must be denominated in the asset's native units. USD valuation, if later provided, must be a separate time-aligned valuation with its own price source, timestamp, and missing-price behavior.

Do not count exchange-to-exchange transfers as external deposits or withdrawals. Keep bridge movements, internal transfers, contract interactions, wrapped-asset mint/burn, staking, and exchange-internal ledger movements separate unless a validated methodology explicitly reconciles them. Avoid double-counting traces and token logs representing the same economic movement.

Report the window boundaries, included chains/assets, attribution tiers, confirmation policy, excluded event classes, and missing-data coverage alongside every aggregate. Never treat a partial scan as a complete market-wide flow.

## 4. Whale and entity uncertainty

- Large transfer thresholds are descriptive filters only. They do not establish a whale identity or beneficial ownership.
- Do not infer that a sender/recipient is an individual, institution, insider, exchange, or fund from transfer size, address balance, or social username.
- Do not deanonymize addresses, connect on-chain addresses to personal identities, or infer common ownership from proximity or shared counterparties alone.
- Do not label an exchange deposit as an intention to sell, or an exchange withdrawal as accumulation. These are possible interpretations, not observations.
- If a future analytics method uses clustering, it must be separately documented, independently evaluated, reversible, and reported as a probabilistic heuristic—not verified ownership.
- Social posts and headlines cannot serve as sole proof of address ownership or transfer intent.

## 5. Quality controls and uncertainty output

Each flow dataset should expose:

- `attribution_tier_counts` and `unknown_address_count`.
- `conflicting_label_count` and `manual_review_required`.
- `coverage_start`, `coverage_end`, `last_complete_block`, and any scan gaps.
- `reorg_or_finality_status`, duplicate-event count, and malformed-event count.
- `source_independence_verified` (default false unless demonstrated) and provider freshness.
- Whether amounts are native units or separately price-valued.
- A clear statement that flow is observed movement, not intent or predicted price direction.

Missing, stale, conflicting, unfinalized, or incomplete evidence must remain visible. Do not replace missing observations with zero.

## 6. Provider and implementation acceptance gates

Before selecting a chain data source, document the current free-tier limits, signup/payment requirements, supported chains, historical depth, rate limits, attribution-label provenance, data licensing, and retention terms. Prefer public, documented, read-only interfaces and avoid adding a card-required or paid dependency to the $0-first baseline.

A future connector must pass:

1. Chain/asset identity and decimal validation.
2. Transaction/event deduplication and deterministic pagination.
3. Timestamp, block-height, confirmation, and reorg handling.
4. Transfer direction and internal/bridge/mint/burn classification tests.
5. Address-label provenance, tiering, expiry, and conflict tests.
6. Partial coverage and provider outage/freshness tests.
7. Reproducible flow calculations with boundary and double-counting fixtures.
8. API contract tests proving read-only behavior and absence of identity overclaim.
9. Separately authorized live smoke tests; mocked tests do not establish provider correctness.

## 7. Explicit exclusions

This methodology does not authorize wallet connection or control, private-key/seed-phrase handling, signing, broadcasting, fund movement, order execution, personal deanonymization, or claims of verified whale identity. CIN remains a read-only research and intelligence system.
