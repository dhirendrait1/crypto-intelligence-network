# CIN Alert Worker Operations

## Scope and safety

The Telegram delivery worker is an optional, read-only notification component. It does not trade, place or manage orders, control wallets, or move funds. The worker is **one-shot**: it processes at most one bounded batch per invocation and does not run continuously or schedule itself.

## Required configuration

Set these environment variables only in the authorized runtime that will execute the worker:

- `CIN_ALERT_DATABASE_PATH`: path to a persistent, writable SQLite database file.
- `CIN_TELEGRAM_BOT_TOKEN`: Telegram bot token.
- `CIN_TELEGRAM_CHAT_ID`: the single approved destination chat ID.

Never commit credentials, print them, or pass the destination through alert payloads. The adapter intentionally uses only the configured destination. Do not use an ephemeral filesystem for durable production alert state: container restarts can erase it. The current SQLite design is single-host/single-writer oriented and is not a multi-instance shared queue.

## Explicit one-shot invocation

After the database and destination are deliberately configured, run:

```sh
python cin_alert_telegram_worker.py --once
```

Optional bounds:

```sh
python cin_alert_telegram_worker.py --once --limit 5 --lease-seconds 300 --max-attempts 5
```

The worker exits after one batch. It is not invoked by API import, startup, or CI tests. No scheduler is included; a scheduler must be separately authorized and configured. Tests mock Telegram requests and never send a real message.

## Result and failure handling

- Successful provider acceptance is recorded as `sent`; it is not an exactly-once delivery guarantee.
- Transient or provider failures are recorded using sanitized error codes and bounded retry scheduling.
- Exhausted attempts or expired leases at the configured attempt limit become dead-letter items. Expired leases below the limit become `uncertain` and require operator reconciliation; retry authorization can produce a duplicate if Telegram accepted the original.
- A worker process crash may leave an item in `sending` until its lease expires; then it becomes `uncertain` below the attempt limit or `dead` at the limit, without an automatic resend.
- Missing configuration is rejected before queue items are claimed.
- Do not paste bot tokens, chat IDs, or private provider responses into issue reports or logs.

## Release acceptance still required

1. Confirm the deployment has a persistent writable database location before enabling alerts.
2. Set secrets and destination in the authorized runtime; no secrets are configured by this code change.
3. Perform a separately approved, controlled live Telegram smoke test.
4. Add and operate a scheduler only after the database durability, duplicate-delivery risk, and monitoring plan are accepted.
5. Validate live health/readiness and deployed revision separately from offline CI.

No Render or Cloudflare settings are changed by this implementation.
