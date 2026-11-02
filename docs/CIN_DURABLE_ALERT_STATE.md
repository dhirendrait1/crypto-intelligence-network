# CIN Durable Alert State — Acceptance Boundary

**Status:** deterministic threshold evaluation and SQLite-backed decision state are implemented with offline regression coverage. This is not yet a complete alert delivery service.

## Implemented

- Evaluate explicit numeric `above` / `below` threshold rules.
- Validate finite values, metric identity, timezone-aware timestamps, and cooldown configuration.
- Persist the last trigger time per rule and one evaluation result per `(rule_id, observation_id)`.
- Use a SQLite write transaction to serialize concurrent evaluations and avoid duplicate trigger decisions for the same observation.
- Optionally enqueue a notification payload in the same transaction as the trigger decision, cooldown state, and audit event.
- Preserve cooldown state across process restarts.

## Not yet implemented

- Scheduler/poller and live market-data subscription.
- Rule CRUD API, authentication, authorization, or user ownership.
- Notification delivery (Telegram/email/push), delivery receipts, retries, or outbox.
- Exactly-once external notification delivery. The outbox is a durable intent queue, not proof of provider delivery; provider-side idempotency and delivery receipts are still required.
- Live market-provider verification or production deployment.

## Storage requirements

SQLite is suitable for an initial single-host deployment only when the database file is on a durable writable filesystem. An ephemeral container filesystem loses state on restart. Multi-instance deployment requires shared transactional storage or a single-writer design. The caller must manage path permissions, backup/retention, and disk monitoring. No secrets or complete market payloads are stored by this module.

## Verification

```bash
python -m pytest -q tests/test_cin_alert_rules.py tests/test_cin_alert_state_store.py
```

The repository CI tests offline behavior; they do not verify live providers, delivery channels, or Render deployment.

## Safety

This capability is informational only. It does not execute trades, route orders, access wallets, use private keys, or move funds.
