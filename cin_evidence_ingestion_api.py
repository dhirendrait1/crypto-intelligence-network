"""Read-only API for allowlisted public evidence ingestion."""
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

try:
    from app.cin_evidence_ingestion import (
        ALLOWED_REPOSITORIES,
        EvidenceSourceError,
        fetch_github_repository_evidence,
    )
except ModuleNotFoundError:
    from cin_evidence_ingestion import (
        ALLOWED_REPOSITORIES,
        EvidenceSourceError,
        fetch_github_repository_evidence,
    )

router = APIRouter(tags=["public evidence ingestion"])


class PublicEvidenceRequest(BaseModel):
    symbol: str = Field(default="ETH", min_length=1, max_length=10)
    repository: str = Field(default="ethereum/go-ethereum", min_length=1, max_length=100)


@router.post("/public-evidence-ingestion")
def public_evidence_ingestion(request: PublicEvidenceRequest) -> dict[str, Any]:
    """Fetch only allowlisted public GitHub metadata; never marks claims verified."""
    if request.symbol.strip().upper() != "ETH":
        raise HTTPException(status_code=400, detail="Milestone 2 currently supports ETH only")
    if request.repository not in ALLOWED_REPOSITORIES:
        raise HTTPException(status_code=400, detail="Repository is not on the public-source allowlist")
    try:
        return fetch_github_repository_evidence(request.repository)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except EvidenceSourceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        # Keep unexpected provider failures from leaking internals to API clients.
        raise HTTPException(status_code=502, detail="Public evidence provider returned an unexpected response") from exc
