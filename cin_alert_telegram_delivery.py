"""Optional Telegram delivery adapter for CIN's read-only alert outbox.

The adapter is only called explicitly by a worker. Credentials come from the
runtime environment; no token, chat ID, or destination is committed to source.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Mapping

from cin_alert_delivery_outbox import (
    claim_due_alerts,
    mark_alert_failed,
    mark_alert_sent,
)


TELEGRAM_API_BASE = "https://api.telegram.org"
MAX_RESPONSE_BYTES = 64_000
REQUEST_TIMEOUT_SECONDS = 10


class TelegramDeliveryError(RuntimeError):
    """Sanitized delivery failure with a stable machine-readable code."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _credentials() -> tuple[str, str]:
    token = os.environ.get("CIN_TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("CIN_TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        raise TelegramDeliveryError("telegram_configuration_missing")
    if len(token) > 512 or len(chat_id) > 128 or any(ord(char) < 32 for char in token + chat_id):
        raise TelegramDeliveryError("telegram_configuration_invalid")
    return token, chat_id


def send_telegram_notification(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Send one plain-text message to the single configured Telegram destination.

    The destination is intentionally not read from payload data, preventing
    untrusted alert contents from choosing where messages are sent.
    """
    if not isinstance(payload, Mapping):
        raise TelegramDeliveryError("telegram_payload_invalid")
    message = payload.get("text")
    if not isinstance(message, str) or not message.strip() or len(message) > 4096:
        raise TelegramDeliveryError("telegram_message_invalid")
    if any((ord(char) < 32 and char not in "\n\r\t") or ord(char) == 127 for char in message):
        raise TelegramDeliveryError("telegram_message_invalid")

    token, chat_id = _credentials()
    endpoint = f"{TELEGRAM_API_BASE}/bot{token}/sendMessage"
    body = json.dumps(
        {"chat_id": chat_id, "text": message, "disable_web_page_preview": True},
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=body,
        headers={"accept": "application/json", "content-type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            if response.status != 200:
                raise TelegramDeliveryError("telegram_http_error")
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        # Never include exception text or request URL: the URL contains the bot token.
        raise TelegramDeliveryError("telegram_http_error") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise TelegramDeliveryError("telegram_network_error") from None
    if len(raw) > MAX_RESPONSE_BYTES:
        raise TelegramDeliveryError("telegram_response_too_large")
    try:
        result = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise TelegramDeliveryError("telegram_invalid_response") from None
    if not isinstance(result, dict) or result.get("ok") is not True:
        raise TelegramDeliveryError("telegram_rejected")
    message_result = result.get("result")
    message_id = message_result.get("message_id") if isinstance(message_result, dict) else None
    return {"provider": "telegram", "accepted": True, "message_id": message_id}


def process_due_telegram_alerts(
    database_path: str,
    *,
    now: datetime | str,
    limit: int = 10,
    lease_seconds: int = 300,
    max_attempts: int = 5,
) -> dict[str, Any]:
    """Deliver a batch of due alerts using configured credentials and outbox state.

    This function is an explicit worker entry point, not a scheduler. Call it
    from an authorized scheduler only after durable storage and destination
    configuration are established.
    """
    # Fail before claiming rows if no destination is configured, so the queue
    # is not consumed by an unconfigured worker.
    _credentials()
    claimed = claim_due_alerts(
        database_path, now=now, limit=limit,
        lease_seconds=lease_seconds, max_attempts=max_attempts,
    )
    results = []
    for item in claimed:
        try:
            sent = send_telegram_notification(item["payload"])
            try:
                state = mark_alert_sent(
                    database_path, item["idempotency_key"],
                    now=now, claim_attempt=item["attempts"],
                )
            except ValueError:
                # A newer claim may own the row now. Do not overwrite its state
                # or mark its attempt failed; the provider may already have accepted
                # this message, so report uncertainty for operator reconciliation.
                results.append({
                    "idempotency_key": item["idempotency_key"],
                    "status": "state_update_failed",
                    "provider_message_id": sent.get("message_id"),
                })
                continue
            results.append({
                "idempotency_key": item["idempotency_key"],
                "status": "sent" if state.get("status") == "sent" else "state_update_failed",
                "provider_message_id": sent.get("message_id"),
            })
        except TelegramDeliveryError as exc:
            try:
                updated = mark_alert_failed(
                    database_path, item["idempotency_key"], now=now,
                    error_code=exc.code, max_attempts=max_attempts, claim_attempt=item["attempts"],
                )
            except ValueError:
                # Another worker may have reclaimed this lease. Never let a stale
                # failure response overwrite the newer attempt's state.
                results.append({
                    "idempotency_key": item["idempotency_key"],
                    "status": "state_update_failed",
                    "error_code": exc.code,
                })
                continue
            results.append({
                "idempotency_key": item["idempotency_key"],
                "status": updated["status"] if updated else "state_update_failed",
                "error_code": exc.code,
            })
    return {
        "provider": "telegram",
        "claimed": len(claimed),
        "results": results,
        "read_only": True,
    }
