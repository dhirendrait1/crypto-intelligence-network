"""Read-only API contract for caller-supplied CIN service monitoring snapshots."""
from typing import Any
from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

router = APIRouter(tags=["monitoring"])


class MonitoringSnapshot(BaseModel):
    """A snapshot supplied by a trusted caller; this endpoint does not poll services."""
    model_config = ConfigDict(extra="forbid")
    health: str = Field(default="unknown", pattern=r"^(healthy|ok|degraded|unavailable|unknown)$")
    readiness: str = Field(default="unknown", pattern=r"^(ready|not_ready|degraded|unavailable|unknown)$")
    provider_status: str = Field(default="unknown", pattern=r"^(healthy|degraded|unavailable|unknown)$")
    freshness: str = Field(default="unknown", pattern=r"^(fresh|stale|unknown)$")
    observed_at: str | None = Field(default=None, max_length=64)
    warnings: list[str] = Field(default_factory=list, max_length=20)


@router.post("/monitoring/status")
def monitoring_status(snapshot: MonitoringSnapshot) -> dict[str, Any]:
    """Summarize supplied status fields; does not claim live checks were performed."""
    values = snapshot.model_dump()
    health = values["health"]
    readiness = values["readiness"]
    provider = values["provider_status"]
    freshness = values["freshness"]

    if "unavailable" in (health, readiness, provider) or readiness == "not_ready":
        status = "unavailable"
    elif "degraded" in (health, readiness, provider) or freshness == "stale":
        status = "degraded"
    elif all(value in ("healthy", "ok") for value in (health,)) and readiness == "ready" and provider == "healthy" and freshness == "fresh":
        status = "healthy"
    else:
        status = "unknown"

    return {
        "status": status,
        "read_only": True,
        "observed_at": values["observed_at"],
        "inputs": {
            "health": health,
            "readiness": readiness,
            "provider_status": provider,
            "freshness": freshness,
        },
        "warnings": values["warnings"],
        "checks_performed": False,
        "note": "Status summarizes caller-supplied fields; CIN did not poll providers or verify freshness in this request.",
    }
