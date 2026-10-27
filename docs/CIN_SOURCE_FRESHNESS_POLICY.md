# CIN Source Freshness Policy Contract

## Purpose

Define how a caller may label a market or intelligence observation as `fresh`, `stale`, or `unknown`. This is an acceptance contract for future source adapters; it does not claim that any provider is currently polled or validated.

## Required observation envelope

Every observation evaluated for freshness must preserve these fields where applicable:

- `source_id`: stable, documented provider/source identifier.
- `instrument_or_subject`: exact asset pair, metric, chain, protocol, or news subject.
- `observed_at`: source event/candle timestamp, not the time CIN received or re-packaged the response.
- `retrieved_at`: time CIN actually retrieved the response, recorded separately.
- `timestamp_semantics`: what the source timestamp means (for example, candle open time, candle close time, publication time, or block time).
- `quote_currency` and `interval`: required for market candles when relevant; never silently equate USD with USDT.
- `provenance`: endpoint/provider identity and any fallback used.

Missing source identity, missing/ambiguous source timestamp semantics, invalid timestamps, or a source timestamp too far in the future must result in `unknown`, not `fresh`.

## Classification rules

1. Select a maximum age policy by source and data type. Do not use one universal threshold for candles, order-book snapshots, on-chain observations, and news.
2. Use a timezone-aware evaluation clock and a timezone-aware source timestamp. A naive timestamp is invalid.
3. A timestamp is `fresh` only when its age is at or below the configured limit.
4. A timestamp older than the limit is `stale`.
5. An invalid timestamp, unknown timestamp meaning, absent provenance, or future timestamp beyond explicitly configured clock-skew tolerance is `unknown`.
6. Small tolerated clock skew may be clamped to zero age, but must not erase or rewrite the original timestamp.
7. Keep `observed_at` and `retrieved_at` distinct. A recent retrieval of old data does not make the underlying observation fresh.
8. For candles, define whether freshness is based on the last *closed* candle. An in-progress candle must not be presented as a completed candle.
9. For fallback providers, record the actual serving provider and preserve the original quote currency and interval. Do not silently blend or relabel data from different providers.
10. An evaluator's output describes timestamp-policy compliance only. It does not prove provider authenticity, completeness, market correctness, or endpoint availability.

## Status aggregation

- `fresh`: all required source-specific freshness evidence for the claim is present and within its configured policy.
- `stale`: valid source evidence exists but exceeds the configured age limit.
- `unknown`: evidence or semantics are missing, invalid, untrusted, or contradictory.
- If required sources conflict, retain the conflict as an explicit warning/status; do not average timestamps or silently select the more convenient result.

A monitoring snapshot's own `observed_at` indicates when the snapshot was recorded. It is not, by itself, proof that underlying provider data is fresh.

## Acceptance tests required before live integration

- Exact freshness limit and one second beyond the limit.
- Naive, malformed, missing, and future timestamps.
- Distinct source-event and retrieval timestamps.
- Old observation retrieved just now remains stale.
- Missing source identity or timestamp semantics remains unknown.
- Closed-candle versus in-progress-candle handling.
- Provider fallback preserves provider identity, pair, quote currency, and interval.
- Contradictory source observations remain explicit.
- Status API continues to state whether checks were actually performed.

## Explicit boundaries

This contract is read-only. It does not authorize order placement/execution, wallet access, funds movement, private-key handling, provider credentials, or financial actions. It does not assert government certification or licensing. Documentation and offline tests are not evidence of live-provider or Render deployment validation.
