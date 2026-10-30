"""Read-only API for allowlisted public evidence ingestion."""
import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from cin_evidence_store import EvidenceStore

try:
    from app.cin_evidence_ingestion import (
        ALLOWED_REPOSITORIES,
        EvidenceSourceError,
        fetch_github_repository_evidence,
    )
except ModuleNotFoundError as exc:
    if exc.name not in {"app", "app.cin_evidence_ingestion"}:
        raise
    from cin_evidence_ingestion import (
        ALLOWED_REPOSITORIES,
        EvidenceSourceError,
        fetch_github_repository_evidence,
    )

router = APIRouter(tags=["public evidence ingestion"])


def get_evidence_store(request: Request) -> EvidenceStore | None:
    """Return an explicitly configured application store; never create one."""
    return getattr(request.app.state, "cin_evidence_store", None)


class PublicEvidenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    symbol: str = Field(default="ETH", min_length=1, max_length=10, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    repository: str = Field(default="ethereum/go-ethereum", min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")

    @field_validator("symbol")
    @classmethod
    def symbol_must_match_full_string(cls, value: str) -> str:
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", value) is None:
            raise ValueError("symbol must contain only supported ticker characters")
        return value

    @field_validator("repository")
    @classmethod
    def repository_must_match_full_string(cls, value: str) -> str:
        if re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", value) is None:
            raise ValueError("repository must use owner/repository syntax")
        return value


@router.post("/public-evidence-ingestion")
def public_evidence_ingestion(
    request: PublicEvidenceRequest,
    store: EvidenceStore | None = Depends(get_evidence_store),
) -> dict[str, Any]:
    """Fetch metadata; injected storage remains unused pending reviewed mapping."""
    if request.symbol.strip().upper() != "ETH":
        raise HTTPException(status_code=400, detail="Milestone 2 currently supports ETH only")
    if request.repository not in ALLOWED_REPOSITORIES:
        raise HTTPException(status_code=400, detail="Repository is not on the public-source allowlist")
    try:
        return fetch_github_repository_evidence(request.repository)
    except EvidenceSourceError as exc:
        # Provider exception text is diagnostic input, not a client-safe message.
        raise HTTPException(
            status_code=502,
            detail="Public evidence provider is temporarily unavailable",
        ) from exc
    except Exception as exc:
        # Never expose provider URLs, response fragments, credentials, or exception text.
        raise HTTPException(
            status_code=502,
            detail="Public evidence provider is temporarily unavailable",
        ) from exc
