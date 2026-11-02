# CIN Mobile Low-Bandwidth and Accessibility Acceptance Contract

**Roadmap:** Stage 6, Steps 32–33. This document defines acceptance criteria; it does not claim a frontend is present or tested.

## Scope

CIN should remain usable on Android phones and constrained connections. The interface is read-only and must not provide order execution, wallet control, fund movement, or private-key entry.

## Network behavior

- Do not poll continuously by default. Refresh is user-initiated or uses a documented bounded interval.
- Bound request timeouts and retries; retries must be finite and use backoff. Never retry indefinitely on rate limits.
- Preserve the last successful payload only with its original retrieval time and an explicit “previous data”/stale label while refresh is pending or failed.
- Do not interpret a timeout, rate limit, malformed payload, or provider outage as a successful empty result.
- Avoid duplicate requests caused by rapid taps; disable or coalesce an in-flight refresh for the same resource.
- Do not request unneeded historical candles or large news bodies for summary cards. Detail views may load additional data on demand when supported.
- Do not cache across assets, quote currencies, intervals, or provider identities unless the cache key includes those dimensions.
- Never infer freshness from the local cache write time; use source observation time or documented retrieval policy.

## Accessible presentation

- Core status must be conveyed in text, not color alone; use readable labels for stale, partial, unknown, and unavailable states.
- Provide visible labels for price, unit, quote currency, interval, source, and timestamp wherever relevant.
- Ensure interactive controls have descriptive accessible names and usable touch targets.
- Keep key content readable at narrow viewport widths and enlarged text sizes without clipping critical warnings.
- Charts must have a text/table alternative that includes units and timestamps. Do not rely on color-only series distinctions.
- Error messages must be sanitized, actionable, and free of stack traces or secrets.
- Honor reduced-motion preferences; avoid animation that obscures changing data.

## Data integrity and safety

- Never substitute zero for missing or invalid numeric values.
- Keep USD and USDT distinct.
- A heuristic score must not be presented as a probability, guarantee, or verified fact.
- A market-data API health response must not be used as evidence that upstream market data is fresh.
- Show missing source or timestamps as unknown rather than fabricating provenance.
- UI actions are limited to viewing, filtering, refreshing, configuring informational alerts where supported, and exporting non-sensitive research data where implemented.

## Acceptance test matrix

1. At a narrow Android viewport, no critical source, unit, timestamp, or warning is clipped.
2. A timeout displays an error state and does not clear a separately labelled last-known result.
3. A rate-limit response does not trigger an unbounded retry loop.
4. Rapid refresh taps do not produce duplicate concurrent requests for the same resource.
5. Empty success and failed request are visibly distinct.
6. Cached data retains its original timestamp and is labelled as previous/stale during refresh failure.
7. Missing timestamps, source, unit, or quote currency are not invented.
8. Charts expose a non-color-only text alternative.
9. Enlarged text and reduced-motion settings do not hide warnings or controls.
10. All core screens remain read-only and contain no order placement or wallet-control affordance.
11. Test artifacts record app revision, device/viewport, connection simulation, and result.
12. Passing unit tests alone is not evidence of Android visual, accessibility, or live-network validation.

## Exit criteria

Steps 32–33 can only be marked implemented after a real interface exists and the matrix is exercised against a recorded revision on small-screen Android layouts and constrained-network conditions. This contract alone does not satisfy those implementation tests.
