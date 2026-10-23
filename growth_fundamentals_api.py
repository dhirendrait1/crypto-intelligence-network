"""Read-only API for CIN growth fundamentals evidence coverage."""
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

try:
    from app.growth_fundamentals_assessment import assess_growth_fundamentals, CATEGORIES
except ModuleNotFoundError:
    from growth_fundamentals_assessment import assess_growth_fundamentals, CATEGORIES

router = APIRouter(tags=["growth fundamentals"])


class GrowthEvidenceRecord(BaseModel):
    category: str = Field(min_length=1, max_length=80)
    source_name: str | None = None
    source_url: str | None = None
    published_at: str | None = None
    status: str = "unverified"
    notes: str | None = None


class GrowthFundamentalsRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=20)
    evidence: list[GrowthEvidenceRecord] = Field(default_factory=list, max_length=200)
    max_age_days: int = Field(default=90, ge=1, le=3650)


@router.post("/growth-fundamentals-assessment")
def growth_fundamentals_assessment_endpoint(
    request: GrowthFundamentalsRequest,
) -> dict[str, Any]:
    """Assess caller-supplied growth evidence metadata; no source documents are fetched."""
    records = [
        item.model_dump() if hasattr(item, "model_dump") else item.dict()
        for item in request.evidence
    ]
    result = assess_growth_fundamentals(
        request.symbol, records, max_age_days=request.max_age_days
    )
    result["evidence_source_mode"] = "caller_supplied_metadata"
    result["source_documents_fetched_by_cin"] = False
    return result
