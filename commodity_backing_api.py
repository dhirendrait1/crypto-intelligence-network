"""Read-only API router for CIN commodity-backed evidence review."""
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.commodity_backing_assessment import assess_commodity_asset

router = APIRouter(tags=["commodity backing evidence"])


class EvidenceRecord(BaseModel):
    evidence_type: str
    source_name: str | None = None
    source_url: str | None = None
    published_at: str | None = None
    checked_at: str | None = None
    status: str = "unverified"
    notes: str | None = None


class CommodityBackingAssessmentRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=20)
    evidence: list[EvidenceRecord] = Field(default_factory=list, max_length=100)
    max_age_days: int = Field(default=90, ge=1, le=3650)


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
