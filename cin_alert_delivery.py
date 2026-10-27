"""Pure state-transition helpers for CIN alert delivery tracking.

No network calls, persistence, scheduler, or notification delivery occur here.
The caller must persist returned state atomically and enforce retry scheduling.
"""
from __future__ import annotations

from typing import Any


_ALLOWED_STATUSES = {"pending", "sending", "delivered", "retry_wait", "failed", "suppressed"}


def initial_delivery_state(event_id: str, max_attempts: int = 3) -> dict[str, Any]:
    """Build a new pending delivery record."""
    if not isinstance(event_id, str) or not event_id.strip():
        raise ValueError("event_id must be a non-empty string")
    if isinstance(max_attempts, bool) or not isinstance(max_attempts, int) or max_attempts < 1:
        raise ValueError("max_attempts must be a positive integer")
    return {
        "event_id": event_id,
        "status": "pending",
        "attempt_count": 0,
        "max_attempts": max_attempts,
        "last_error_code": None,
        "delivered_at": None,
    }


def record_delivery_attempt(state: dict[str, Any]) -> dict[str, Any]:
    """Transition a pending/retry-wait record to sending, or fail closed."""
    if not isinstance(state, dict):
        return {"status": "invalid_state", "reason": "state_must_be_object"}
    required = ("event_id", "status", "attempt_count", "max_attempts")
    if any(key not in state for key in required):
        return {**state, "status": "invalid_state", "reason": "required_fields_missing"}
    count, limit = state["attempt_count"], state["max_attempts"]
    if (isinstance(count, bool) or not isinstance(count, int) or count < 0
            or isinstance(limit, bool) or not isinstance(limit, int) or limit < 1
            or count > limit):
        return {**state, "status": "invalid_state", "reason": "invalid_attempt_counters"}
    if state["status"] not in {"pending", "retry_wait"}:
        return {**state, "reason": "status_not_attemptable"}
    if count >= limit:
        return {**state, "status": "failed", "reason": "attempt_limit_reached"}
    return {**state, "status": "sending", "attempt_count": count + 1, "last_error_code": None}


def record_delivery_result(
    state: dict[str, Any],
    *,
    succeeded: bool,
    error_code: str | None = None,
    delivered_at: str | None = None,
) -> dict[str, Any]:
    """Record a completed attempt. Failure is retryable only while attempts remain."""
    if not isinstance(state, dict) or state.get("status") != "sending":
        return {
            **(state if isinstance(state, dict) else {}),
            "status": "invalid_state",
            "reason": "result_requires_sending_state",
        }
    if not isinstance(succeeded, bool):
        return {**state, "status": "invalid_state", "reason": "succeeded_must_be_boolean"}
    if succeeded:
        if not isinstance(delivered_at, str) or not delivered_at.strip():
            return {**state, "reason": "delivery_timestamp_required"}
        return {**state, "status": "delivered", "delivered_at": delivered_at, "last_error_code": None}
    if not isinstance(error_code, str) or not error_code.strip():
        return {**state, "reason": "failure_error_code_required"}
    count, limit = state.get("attempt_count"), state.get("max_attempts")
    if (isinstance(count, bool) or not isinstance(count, int) or count < 1
            or isinstance(limit, bool) or not isinstance(limit, int) or limit < 1):
        return {**state, "status": "invalid_state", "reason": "invalid_attempt_counters"}
    status = "retry_wait" if count < limit else "failed"
    return {**state, "status": status, "last_error_code": error_code, "delivered_at": None}
