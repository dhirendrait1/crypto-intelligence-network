# CIN Cross-Source Evidence Comparison

## Purpose

`cross_source_evidence.py` provides a read-only comparison primitive for caller-supplied observations of the same metric. It groups observations by exact metric name and unit, then compares observations whose timestamps fall within a configurable time window (default: 300 seconds).

## Comparison and confidence rules

- Every observation must include a metric, unit, finite numeric value, timezone-aware `observed_at`, source name, and absolute HTTP(S) source URL without embedded credentials. Invalid observations are counted and excluded.
- URL identity is normalized for scheme/hostname case, default ports, and trailing path slash. Repeated observations from the same normalized URL do not count as multiple sources.
- Different units are never combined. Observations outside the configured time window are counted but excluded from the comparison.
- For two or more distinct normalized source URLs, CIN compares the value range against `max(absolute_tolerance, relative_tolerance * abs(median_value))`. Defaults are 0 absolute and 1% relative tolerance.
- A spread within tolerance is `agreement_observed` with `limited_corroboration`. A spread above tolerance is `conflicting` with `low_confidence_conflict`. Fewer than two distinct source URLs yields `insufficient_independent_source_count` and `insufficient_evidence`.
- No numeric probability is emitted. No source is ranked, trusted, or selected as the winner. Source independence and source-role authentication always remain false.

## Interpretation boundary

Agreement between two URLs is not proof of independent ownership, authorship, audit, or source quality. This helper does not fetch source data, validate the underlying metric methodology, adjust values across units, or persist history. Tolerance values are comparison heuristics, not accuracy guarantees. Confidence classes describe the observed evidence agreement only; they are not investment advice or a trade signal.

The helper is not wired to a production endpoint in this increment. API integration and live-source validation remain separate acceptance work.


## Read-only API integration

The FastAPI router exposes `POST /cross-source-evidence-comparison`. It accepts 1–500 caller-supplied observations, with explicit optional `absolute_tolerance`, `relative_tolerance` (0–1), and `comparison_window_seconds` (0–86400). The route rejects unknown fields and does not fetch or persist source data. The deployment scaffold patch copies both the comparison module and API router into the app and registers the router idempotently.

API integration tests cover agreement/conflict responses, confidence labels, batch bounds, unknown fields, and tolerance/window validation. Passing offline tests does not establish live source accuracy or deployed endpoint availability.
