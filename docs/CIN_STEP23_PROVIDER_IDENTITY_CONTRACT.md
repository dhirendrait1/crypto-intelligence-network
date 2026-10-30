# CIN Step 23 — Provider Evidence Identity Contract

**Status:** Implemented in the local SQLite reference adapter; provider-specific canonicalization remains the responsibility of each source adapter.

## 1. Identity tuple

A provider-backed evidence record is identified by the pair:

- `source_namespace`: a stable identifier for the provider/API or source namespace.
- `external_evidence_id`: the provider's identifier for the source object.

The pair is unique when `external_evidence_id` is not NULL. A NULL external identifier is not part of the provider-identity uniqueness constraint.

## 2. Whitespace policy

The current SQLite adapter trims leading and trailing whitespace from both identity components before storing a bundle. Identity lookup applies the same trim operation.

- Padded and unpadded forms therefore resolve to the same identity.
- Empty or whitespace-only values are rejected.
- Internal whitespace is not rewritten.
- The raw source payload and observation metadata are not rewritten by identity normalization.

The trim operation is an adapter-level boundary rule, not a claim that every upstream provider treats whitespace identically. Provider adapters should validate and supply the provider's canonical identifier before persistence.

## 3. Case policy

The SQLite unique index uses the default binary text comparison. The adapter does not lowercase or case-fold identity values.

- `Asset-A` and `asset-a` are distinct identities.
- A source adapter must apply case normalization only when the upstream provider contract explicitly defines identifiers as case-insensitive.
- Any provider-specific normalization must be deterministic and applied consistently before both storage and lookup.

Do not introduce global case folding: it can collapse distinct provider objects.

## 4. Length and validation

The reference schema constrains trimmed `source_namespace` values to 1–128 characters and non-NULL `external_evidence_id` values to 1–256 characters. The adapter enforces the same bounds for bundle creation. Identity lookup rejects empty values; database/schema constraints remain the final storage guard.

## 5. Uniqueness and concurrent ingestion

The SQLite reference migration defines a partial unique index over `(source_namespace, external_evidence_id)` for non-NULL external IDs. Concurrent first ingestion may therefore produce a unique-constraint conflict. The opt-in persistence orchestration recovers only SQLite's UNIQUE constraint error, looks up the winning record, and appends a new observation. Other integrity errors must propagate.

## 6. Portability requirements for future adapters

A future storage adapter must preserve the following contract or document a deliberate, provider-specific deviation:

1. Use the composite identity tuple; do not identify records by external ID alone.
2. Treat NULL external IDs as unkeyed unless a separate stable identity strategy is specified.
3. Apply the same normalization to identity writes and lookups.
4. Preserve case unless the provider explicitly defines case-insensitive IDs.
5. Enforce uniqueness atomically at the storage boundary, not only with a pre-insert lookup.
6. Keep identity normalization separate from raw evidence payload, provenance timestamps, and observation metadata.
7. Surface unrelated validation, foreign-key, and storage failures; never misreport them as duplicate-identity races.

## 7. Scope and limitations

This contract describes the Step 23 local SQLite reference implementation and requirements for future adapters. It does not make SQLite a production backend, authenticate provider data, guarantee upstream identifier stability, or authorize API writes. The persistence orchestration remains opt-in and is not wired into the public API. No trade execution, wallet, or fund-movement capability is introduced.
