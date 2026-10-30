"""Read-only API for comparing caller-supplied cross-source metric observations."""
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

try:
    from app.cross_source_evidence import compare_metric_observations
except ModuleNotFoundError:
    from cross_source_evidence import compare_metric_observations

router = APIRouter(tags=["cross-source evidence"])


class MetricObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    metric: str = Field(min_length=1, max_length=100)
    unit: str = Field(min_length=1, max_length=40)
    value: float = Field(strict=True, allow_inf_nan=False)
    source_name: str = Field(min_length=1, max_length=200)
    source_url: str = Field(min_length=1, max_length=2048)
    observed_at: str = Field(min_length=1, max_length=64)


class CrossSourceComparisonRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    observations: list[MetricObservation] = Field(min_length=1, max_length=500)
    absolute_tolerance: float = Field(default=0.0, ge=0, allow_inf_nan=False)
    relative_tolerance: float = Field(default=0.01, ge=0, le=1, allow_inf_nan=False)
    comparison_window_seconds: int = Field(default=300, strict=True, ge=0, le=86400)


@router.post("/cross-source-evidence-comparison")
def cross_source_evidence_comparison_endpoint(
    request: CrossSourceComparisonRequest,
) -> dict[str, Any]:
    """Compare submitted observations; no source data is fetched or stored."""
    observations = [
        item.model_dump() if hasattr(item, "model_dump") else item.dict()
        for item in request.observations
    ]
    return compare_metric_observations(
        observations,
        absolute_tolerance=request.absolute_tolerance,
        relative_tolerance=request.relative_tolerance,
        comparison_window_seconds=request.comparison_window_seconds,
    )
