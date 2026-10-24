"""Read-only API router for CIN commodity-backed evidence review."""
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

try:
    from app.commodity_backing_assessment import assess_commodity_asset
except ModuleNotFoundError:  # Allows offline tests from the repository root.
    from commodity_backing_assessment import assess_commodity_asset

router = APIRouter(tags=["commodity backing evidence"])


class EvidenceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evidence_type: str = Field(min_length=1, max_length=80)
    source_name: str | None = Field(default=None, max_length=200)
    source_url: str | None = Field(default=None, max_length=2048)
    published_at: str | None = Field(default=None, max_length=64)
    checked_at: str | None = Field(default=None, max_length=64)
    status: str = Field(default="unverified", max_length=32)
    notes: str | None = Field(default=None, max_length=2000)


class CommodityBackingAssessmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    symbol: str = Field(min_length=1, max_length=20, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*\z")
    evidence: list[EvidenceRecord] = Field(default_factory=list, max_length=100)
    max_age_days: int = Field(default=90, strict=True, ge=0, le=3650)


@router.post("/commodity-backing-assessment")
def commodity_backing_assessment_endpoint(
    request: CommodityBackingAssessmentRequest,
) -> dict[str, Any]:
    """Assess submitted evidence metadata; this endpoint does not fetch or certify evidence."""
    records = [item.model_dump() if hasattr(item, "model_dump") else item.dict() for item in request.evidence]
    result = assess_commodity_asset(
        request.symbol,
        records,
        max_age_days=request.max_age_days,
    )
    result["evidence_source_mode"] = "caller_supplied_metadata"
    result["source_documents_fetched_by_cin"] = False
    return result
