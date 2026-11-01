"""Opt-in, read-only HTTP adapter for source-labelled CIN shortlist snapshots.

This router is NOT automatically mounted in production or the Render patch.
Request scores are caller-supplied and not independently verified.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

try:
    from app.cin_shortlist_evidence import assess_evidence
except ModuleNotFoundError as exc:
    if exc.name not in {"app", "app.cin_shortlist_evidence"}:
        raise
    from cin_shortlist_evidence import assess_evidence

router = APIRouter(tags=["shortlist-offline-research"])


class FactorEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    score: float = Field(ge=0, le=100, allow_inf_nan=False)
    source: str = Field(min_length=1, max_length=160)
    observed_at: str = Field(min_length=1, max_length=64)


class ShortlistCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    symbol: str = Field(min_length=1, max_length=24, pattern=r"^[A-Za-z0-9._-]+$")
    factors: dict[str, FactorEvidence]
    gates: dict[str, bool]


class ShortlistRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    candidates: list[ShortlistCandidate] = Field(max_length=100)


@router.post("/research/shortlist/evaluate")
def evaluate_shortlist(request: ShortlistRequest) -> dict[str, Any]:
    """Compute only on supplied evidence; never fetch market data or execute trades."""
    seen: set[str] = set()
    results: list[dict[str, Any]] = []
    for candidate in request.candidates:
        if candidate.symbol in seen:
            raise HTTPException(status_code=400, detail="Duplicate candidate symbol")
        seen.add(candidate.symbol)
        try:
            result = assess_evidence(
                candidate.symbol,
                {name: evidence.model_dump() for name, evidence in candidate.factors.items()},
                candidate.gates,
                max_age=timedelta(hours=24),
            )
        except (ValueError, TypeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        results.append(result)
    eligible = sorted(
        (r for r in results if r["status"] == "shortlist_eligible"),
        key=lambda r: (-float(r["score"]), r["symbol"]),
    )
    excluded = sorted(
        (r for r in results if r["status"] != "shortlist_eligible"),
        key=lambda r: (r["status"], r["symbol"]),
    )
    return {
        "mode": "caller_supplied_offline_research",
        "source_verification": "not_independently_verified",
        "execution_enabled": False,
        "results": eligible + excluded,
    }
