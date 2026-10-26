# CIN Alert Delivery Outbox — Initial Acceptance Boundary

**Status:** durable queue state and retry scheduling primitives are implemented with offline tests. No notification provider is connected.

## Included

- Idempotent enqueue by caller-provided key (recommended: `rule_id:observation_id:channel`).
- Atomic worker claims for due queue items using SQLite transactions.
- Explicit `pending`, `sending`, `sent`, and terminal `failed` states.
- Bounded exponential retry delay, maximum-attempt policy, and bounded error text.
- JSON payload validation; rejects non-finite numbers and non-serializable values.
- Concurrent enqueue/claim regression tests.

## Required integration before production

1. When an alert decision is triggered, enqueue a small notification payload in the same durable workflow as the alert event. The current evaluator and outbox are separate primitives; a transaction spanning both is not yet provided.
2. Add a delivery adapter (for example, Telegram Bot API) that reads a claimed item and sends only to an authorized configured destination.
3. Mark success only after the provider confirms acceptance; on retryable failure call `mark_notification_failed`.
4. Add recovery for workers that crash while an item is `sending`. Current outbox does not reclaim abandoned `sending` rows automatically.
5. Add authorization, secret management, retention policy, rate limits, and operational monitoring before exposing this through an API.

## Delivery semantics

This is an **at-least-once-oriented queue primitive**, not an exactly-once delivery guarantee. A worker can send a notification and crash before recording success; retry may send it again unless the provider or adapter supports idempotency. Do not claim that a notification was delivered merely because it was queued.

## Storage and hosting

SQLite needs a durable writable filesystem. Ephemeral container filesystems lose queue state on restart; multiple service instances require shared transactional storage or a single-writer deployment. Do not use local SQLite in a horizontally scaled service without an explicit persistence strategy. The module sends no network requests itself and stores no provider credentials.

## Verification

```bash
python -m pytest -q tests/test_cin_alert_outbox.py
```

Offline tests do not validate a live delivery provider or Render behavior.

## Safety boundary

Notifications are informational. This module does not execute trades, route orders, access wallets, use private keys, or move funds.
