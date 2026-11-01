"""Unmounted, disabled-by-default dashboard contract for Coinbase research.

This router has no production registration. Opt-in requires BOTH explicit
staging inclusion and CIN_COINBASE_RESEARCH_ENABLED=1 at request time.
No order execution, wallet access, accounts, or private keys.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, ConfigDict, Field

from cin_coinbase_status_shortlist_pipeline import research_liquidity_with_market_status
from cin_coinbase_public_orderbook import PublicBookError
from cin_coinbase_staging_guard import require_staging_access, reserve_research_budget

router = APIRouter(tags=["coinbase-shortlist-research-staging"])
ALLOWED_PRODUCTS = frozenset(("BTC-USD", "ETH-USD"))


class MarketEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str = Field(min_length=1, max_length=100)
    symbol: str = Field(min_length=2, max_length=20, pattern=r"^[A-Z0-9]+$")
    currency: str = Field(min_length=2, max_length=12, pattern=r"^[A-Z0-9]+$")
    price: float = Field(gt=0, allow_inf_nan=False)
    last_updated: str = Field(min_length=1, max_length=64)
    freshness_status: str = Field(min_length=1, max_length=20)
    analysis_eligible: bool
    total_volume_24h: float | None = Field(default=None, ge=0, allow_inf_nan=False)


class ResearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    market: MarketEvidence


@router.post("/research/coinbase/market-eligibility", dependencies=[Depends(require_staging_access)])
def evaluate_coinbase_market(request: ResearchRequest) -> dict[str, Any]:
    """Return dashboard-safe evidence; never expose provider internals or books."""
    product = f"{request.market.symbol}-{request.market.currency}"
    if product not in ALLOWED_PRODUCTS:
        raise HTTPException(status_code=400, detail="Unsupported research market")
    reserve_research_budget()
    try:
        result = research_liquidity_with_market_status(request.market.model_dump())
    except (PublicBookError, OSError, TimeoutError):
        raise HTTPException(status_code=503, detail="Public market provider unavailable") from None
    except (ValueError, TypeError, ArithmeticError):
        raise HTTPException(status_code=422, detail="Invalid or inconsistent market evidence") from None
    if result.get("execution_enabled") is not False:
        raise HTTPException(status_code=503, detail="Research integrity check failed")
    status = result.get("eligibility_status", result.get("status"))
    if status not in {"rejected", "insufficient_data"}:
        # Positive shortlist approval is impossible until independently
        # authenticated factor and market-row evidence is available.
        raise HTTPException(status_code=503, detail="Research integrity check failed")
    evidence = result.get("eligibility_evidence")
    if not isinstance(evidence, dict):
        evidence = {
            "data_reliable": None, "liquidity_sufficient": None,
            "security_clear": None, "risk_acceptable": None,
        }
    if any(v is True for k, v in evidence.items() if k in {"liquidity_sufficient", "security_clear", "risk_acceptable"}):
        raise HTTPException(status_code=503, detail="Research integrity check failed")
    return {
        "schema_version": "cin-coinbase-market-eligibility-v1",
        "product_id": product,
        "status": status,
        "reason": result.get("reason", "Insufficient verified evidence"),
        "market_status": result.get("product_status"),
        "book_requested": result.get("book_requested", False),
        "eligibility_evidence": evidence,
        "provider": "coinbase",
        "market_row_provenance": "caller_supplied_not_independently_verified",
        "shortlist_approved": False,
        "execution_enabled": False,
    }
