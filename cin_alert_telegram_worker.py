"""One-shot, explicitly invoked CIN Telegram outbox worker.

This is not a scheduler and does not start on import. It processes one bounded
batch only when executed by an authorized operator or external scheduler.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

from cin_alert_telegram_delivery import (
    TelegramDeliveryError,
    process_due_telegram_alerts,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Process one bounded batch of read-only CIN Telegram alerts."
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="required explicit acknowledgement to process one batch",
    )
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--lease-seconds", type=int, default=300)
    parser.add_argument("--max-attempts", type=int, default=5)
    args = parser.parse_args(argv)

    if not args.once:
        parser.error("pass --once to explicitly authorize one batch")
    database_path = os.environ.get("CIN_ALERT_DATABASE_PATH", "").strip()
    if not database_path or database_path == ":memory:":
        print(
            json.dumps({"status": "error", "error_code": "alert_database_path_missing"}),
            file=sys.stderr,
        )
        return 2

    try:
        result = process_due_telegram_alerts(
            database_path,
            now=datetime.now(timezone.utc),
            limit=args.limit,
            lease_seconds=args.lease_seconds,
            max_attempts=args.max_attempts,
        )
    except TelegramDeliveryError as exc:
        print(
            json.dumps({"status": "error", "error_code": exc.code}),
            file=sys.stderr,
        )
        return 2
    except Exception as exc:
        # Do not print exception text: it may contain filesystem or provider details.
        print(
            json.dumps({
                "status": "error",
                "error_code": "alert_worker_failed",
                "error_type": type(exc).__name__,
            }),
            file=sys.stderr,
        )
        return 1

    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
