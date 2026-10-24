"""Read-only API for CIN growth fundamentals evidence coverage."""
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

try:
    from app.growth_fundamentals_assessment import assess_growth_fundamentals, CATEGORIES
except ModuleNotFoundError:
    from growth_fundamentals_assessment import assess_growth_fundamentals, CATEGORIES

router = APIRouter(tags=["growth fundamentals"])


class GrowthEvidenceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category: str = Field(min_length=1, max_length=80)
    source_name: str | None = Field(default=None, max_length=200)
    source_url: str | None = Field(default=None, max_length=2048)
    published_at: str | None = Field(default=None, max_length=64)
    status: str = Field(default="unverified", max_length=32)
    notes: str | None = Field(default=None, max_length=2000)


class GrowthFundamentalsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    symbol: str = Field(min_length=1, max_length=20, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    evidence: list[GrowthEvidenceRecord] = Field(default_factory=list, max_length=200)
    max_age_days: int = Field(default=90, strict=True, ge=0, le=3650)


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
