# CIN Alert Evaluation, Durable State, and Delivery Outbox

**Status:** deterministic threshold evaluation, durable decision state, and a transport-neutral delivery outbox have offline regression coverage. This is still not a complete live notification service.

## Included

- Evaluate numeric `above` / `below` threshold rules with metric identity, finite-value and timestamp validation.
- Persist one evaluation per `(rule_id, observation_id)` and per-rule cooldown state in SQLite.
- Serialize concurrent evaluations and duplicate outbox enqueues with transactional writes and idempotency keys.
- Queue notification intent, claim due items, record success, retry sanitized failures with bounded exponential backoff, and mark exhausted retries as terminal `dead` letters.
- Keep notification transport separate. No network request is made by these modules.

## Caller responsibilities and limitations

- A caller must supply market observations and invoke evaluation. No scheduler, market-data poller, rule CRUD API, authentication, or per-user rule ownership is implemented here.
- A separate authorized delivery adapter must claim outbox entries, send them to the configured channel, and record the result. No Telegram/email/push message is sent by the outbox.
- The evaluator/state store and delivery outbox are separate primitives; they are not yet committed in a single cross-module transaction.
- A crash after an external provider accepts a message but before CIN records success can lead to duplicate delivery on retry. Use the outbox idempotency key with provider-side idempotency where supported; otherwise delivery is at-least-once, not exactly-once.
- Items left in `sending` after a worker crash are not automatically reclaimed yet; worker-lease recovery remains required.
- SQLite is appropriate only for a single host with durable writable storage. An ephemeral filesystem loses state after restart; multiple service instances need shared transactional storage or a single-writer design.
- Configure filesystem permissions, retention, backup and disk monitoring. Store only minimal alert payloads and never place credentials in the outbox.

## Verification

```bash
python -m pytest -q tests/test_cin_alert_rules.py tests/test_cin_alert_state_store.py tests/test_cin_alert_delivery_outbox.py
```

Offline tests do not verify live market providers, notification credentials, external delivery, or Render deployment.

## Safety boundary

CIN alerting is informational only: no order execution, wallet access, private keys, fund movement, or trade execution is implemented.
