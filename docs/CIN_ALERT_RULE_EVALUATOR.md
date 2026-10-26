# CIN Alert Rule Evaluator — Initial Acceptance Boundary

**Status:** deterministic evaluation primitive implemented with offline regression tests; not an end-to-end alert delivery system.

## Supported behavior

- Evaluate a named numeric observation against an explicit `above` or `below` threshold.
- Require matching metric identity and timezone-aware observation/evaluation timestamps.
- Reject malformed rule configuration, booleans/non-finite numeric values, future observations, and invalid cooldown values.
- Return an auditable result containing rule ID, observation ID, threshold, observed value, observation time, evaluation time, status, and reason.
- Suppress a previously processed observation ID and suppress matching observations while a caller-provided cooldown is active.

## Deliberate limitations

- This module is pure and read-only. It does not fetch prices, subscribe to a market feed, persist rules or delivery state, schedule evaluations, send Telegram/email/push notifications, or execute orders.
- The caller must persist the last event ID and last trigger timestamp durably. Without that external state, deduplication/cooldown cannot survive process restarts.
- This first increment does not establish user-configurable rule CRUD, authentication/authorization, retries, delivery receipts, or production monitoring.
- Threshold crossings are evaluated against the supplied observation; this is not a forecast and is not investment advice.

## Verification

Run the focused tests with:

```bash
python -m pytest -q tests/test_cin_alert_rules.py
```

The repository CI workflow also runs the offline test suite. Passing mocked/offline tests does not verify live market feeds, persistent state, or notification delivery.

## Safety boundary

CIN alert evaluation is informational only. No account credentials, wallet access, private keys, funds movement, order placement, or trade execution are used.
