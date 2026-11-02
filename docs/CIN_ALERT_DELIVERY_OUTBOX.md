# CIN Alert Evaluation, Durable State, and Delivery Outbox

**Status:** deterministic threshold evaluation, durable decision state, and a transport-neutral delivery outbox have offline regression coverage. This is still not a complete live notification service.

## Included

- Evaluate numeric `above` / `below` threshold rules with metric identity, finite-value and timestamp validation.
- Persist one evaluation per `(rule_id, observation_id)` and per-rule cooldown state in SQLite.
- Serialize concurrent evaluations and duplicate outbox enqueues with transactional writes and idempotency keys.
- Queue notification intent, claim due items, record success, retry sanitized failures with bounded exponential backoff, and mark exhausted retries as terminal `dead` letters.
- When a `sending` lease expires, move it to `uncertain` (below the attempt limit) or `dead` (at the attempt limit); never automatically reclaim and resend an expired send with unknown provider outcome. Claims are serialized using SQLite `BEGIN IMMEDIATE` for the supported single-host/single-writer model. An operator can explicitly resolve an uncertain item as sent or authorize a retry with duplicate-risk recorded.
- Keep notification transport separate. The outbox module itself makes no network request.

## Caller responsibilities and limitations

- A caller must supply market observations and invoke evaluation. No scheduler, market-data poller, rule CRUD API, authentication, or per-user rule ownership is implemented here.
- A separate explicitly invoked delivery adapter must claim outbox entries, send them to the configured channel, and record the result. No Telegram/email/push message is sent merely by importing these modules or starting the API.
- The evaluation decision, cooldown state, audit event, and pending outbox intent are committed together by `evaluate_and_record()` in one SQLite transaction. Later worker claims, provider outcomes, lease recovery, and operator reconciliation are separate transactions; the external provider send is not part of the database transaction.
- A crash after an external provider accepts a message but before CIN records success leaves an uncertain outcome. CIN does not automatically retry that expired lease. An operator may mark it sent or explicitly authorize a retry; retry authorization can create a duplicate if the provider accepted the original. Delivery is **not exactly-once**.
- `updated_at` acts as the lease timestamp; this implementation does not renew leases while a send is in progress. Keep provider calls shorter than the configured lease. If a lease expires during a slow provider call, the item becomes `uncertain` (or `dead` at the attempt limit) and is not automatically resent; an operator must reconcile it. Each claim increments an attempt generation, and completion/failure updates must match that generation and arrive before the configured lease expires. The adapter timestamps success/failure acknowledgements with its completion clock (injectable for deterministic tests), rather than reusing the batch's claim timestamp. An acknowledgement after expiry is rejected even if lease recovery has not yet run; a subsequent recovery marks the outcome uncertain (or dead at the attempt limit). This fencing protects local state; it cannot retract a duplicate message already accepted by the provider.
- Retry attempts are bounded. Once an item reaches `dead`, the claim query does not reclaim it automatically; investigate and manually reconcile terminal items before any deliberate replay.
- SQLite is appropriate only for a single host with durable writable storage. An ephemeral filesystem loses state after restart; multiple service instances need shared transactional storage or a single-writer design.
- Configure filesystem permissions, retention, backup and disk monitoring. Store only minimal alert payloads and never place credentials in the outbox.

## Verification

```bash
python -m pytest -q tests/test_cin_alert_rules.py tests/test_cin_alert_state_store.py tests/test_cin_alert_delivery_outbox.py
```

Offline tests cover duplicate enqueue, serialized claims, active/expired leases, bounded retries, dead-letter behavior and mocked transport responses. They do not verify live market providers, notification credentials, external delivery, persistent production storage, or Render deployment.

## Safety boundary

CIN alerting is informational only: no order execution, wallet access, private keys, fund movement, or trade execution is implemented.
