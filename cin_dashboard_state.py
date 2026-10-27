"""Deterministic presentation-state normalization for CIN dashboard adapters.

This module does not fetch data, mutate API payloads, persist state, or imply that
a frontend or any API capability is deployed.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Literal

DashboardState = Literal["loading", "ready", "empty", "partial", "stale", "error", "unavailable"]
Freshness = Literal["fresh", "stale", "unknown"]


@dataclass(frozen=True)
class DashboardViewState:
    """Presentation metadata kept separate from the original response payload."""

    state: DashboardState
    data: Any = None
    source: str | None = None
    observed_at: str | None = None
    retrieved_at: str | None = None
    freshness: Freshness = "unknown"
    warnings: tuple[str, ...] = ()
    error_code: str | None = None


def normalize_dashboard_state(
    *,
    data: Any = None,
    response_received: bool = False,
    capability_available: bool = True,
    error_code: str | None = None,
    freshness: str = "unknown",
    partial: bool = False,
    source: str | None = None,
    observed_at: str | None = None,
    retrieved_at: str | None = None,
    warnings: Iterable[str] = (),
) -> DashboardViewState:
    """Normalize request metadata without inventing missing evidence.

    Priority: current-request error, unsupported capability, loading, known
    stale data, partial response, confirmed empty success, then ready.
    A successful empty response must be explicit (for example data=[]).
    """
    normalized_freshness: Freshness = freshness if freshness in ("fresh", "stale") else "unknown"
    safe_warnings = tuple(str(item) for item in warnings if item is not None)
    normalized_source = source.strip() if isinstance(source, str) and source.strip() else None
    normalized_observed = observed_at.strip() if isinstance(observed_at, str) and observed_at.strip() else None
    normalized_retrieved = retrieved_at.strip() if isinstance(retrieved_at, str) and retrieved_at.strip() else None

    if error_code:
        state: DashboardState = "error"
    elif not capability_available:
        state = "unavailable"
    elif not response_received:
        state = "loading"
    elif normalized_freshness == "stale":
        state = "stale"
    elif partial:
        state = "partial"
    elif data is None or data == [] or data == {}:
        state = "empty"
    else:
        state = "ready"

    return DashboardViewState(
        state=state, data=data, source=normalized_source,
        observed_at=normalized_observed, retrieved_at=normalized_retrieved,
        freshness=normalized_freshness, warnings=safe_warnings, error_code=error_code,
    )
