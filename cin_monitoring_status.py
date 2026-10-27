"""Pure read-only aggregation of CIN service and data-quality status."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

MonitoringStatus = Literal["healthy", "degraded", "unavailable", "unknown"]


@dataclass(frozen=True)
class MonitoringSummary:
    status: MonitoringStatus
    service_health: str
    readiness: str
    data_freshness: str
    provider_status: str
    reasons: tuple[str, ...]


def summarize_monitoring_status(
    *,
    health_ok: bool | None,
    ready: bool | None,
    data_freshness: str = "unknown",
    provider_ok: bool | None = None,
) -> MonitoringSummary:
    """Combine supplied observations without polling or guessing timestamps.

    A healthy HTTP process is not enough to call market data healthy. Unknown
    freshness remains unknown; callers must apply documented, endpoint-specific
    thresholds before passing fresh/stale. This function performs no I/O.
    """
    freshness = data_freshness if data_freshness in ("fresh", "stale") else "unknown"
    health_label = "healthy" if health_ok is True else "unhealthy" if health_ok is False else "unknown"
    ready_label = "ready" if ready is True else "not_ready" if ready is False else "unknown"
    provider_label = "healthy" if provider_ok is True else "unhealthy" if provider_ok is False else "unknown"
    reasons: list[str] = []

    if health_ok is False:
        reasons.append("service_health_check_failed")
    if ready is False:
        reasons.append("service_not_ready")
    if provider_ok is False:
        reasons.append("provider_unavailable")
    if freshness == "stale":
        reasons.append("market_data_stale")

    if health_ok is False or ready is False:
        status: MonitoringStatus = "unavailable"
    elif provider_ok is False or freshness == "stale":
        status = "degraded"
    elif health_ok is True and ready is True and provider_ok is True and freshness == "fresh":
        status = "healthy"
    else:
        status = "unknown"
        if freshness == "unknown":
            reasons.append("market_data_freshness_unknown")
        if provider_ok is None:
            reasons.append("provider_status_unknown")
        if health_ok is None or ready is None:
            reasons.append("service_status_unknown")

    return MonitoringSummary(
        status=status,
        service_health=health_label,
        readiness=ready_label,
        data_freshness=freshness,
        provider_status=provider_label,
        reasons=tuple(dict.fromkeys(reasons)),
    )
