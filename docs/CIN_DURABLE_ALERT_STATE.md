# CIN Durable Alert State Store — Initial Acceptance Boundary

**Status:** SQLite-backed persistence is implemented with offline regression tests. This is not a complete alert delivery service.

## Included

- Persist the last successful trigger timestamp for each rule.
- Persist one evaluation decision per `(rule_id, observation_id)` pair.
- Serialize concurrent evaluations with a SQLite write transaction so a repeated event cannot trigger twice.
- Preserve cooldown state across process restarts.
- Store bounded decision metadata only; provider credentials and complete market payloads are not stored.
- Keep the evaluator read-only and independent from exchange account or order APIs.

## Usage boundary

The caller must explicitly invoke `evaluate_and_record(database_path, rule, observation, now=...)` whenever it has an observation to evaluate. This module does not schedule polling, fetch market data, configure rules over HTTP, or send Telegram/email/push messages. The returned `trigger: true` is a decision for a future delivery adapter; it is not proof that a notification was sent.

## Operational notes

- SQLite is suitable for a single-host initial deployment where the database file is on a durable writable disk. Ephemeral filesystems lose state on restart; a multi-instance service needs a shared transactional database or single-writer architecture.
- The caller must decide the database path and ensure filesystem permissions, backup/retention, and disk monitoring.
- Exactly-once notification delivery is not guaranteed: a process can crash after recording a trigger but before sending it. A later delivery-outbox increment should model pending/sending/sent/failed states, retry policy, and idempotency keys.
- Live market-source freshness, authentication, user-specific rule ownership, and delivery credentials remain separate acceptance work.

## Verification

Run:

```bash
python -m pytest -q tests/test_cin_alert_rules.py tests/test_cin_alert_state_store.py
```

CI tests are offline and do not establish live provider or deployment behavior.

## Safety boundary

No trade execution, order routing, wallet access, private keys, or fund movement is implemented.
