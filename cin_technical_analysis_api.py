"""Read-only HTTP endpoint for caller-supplied OHLC technical analysis."""
from typing import Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, ConfigDict

try:
    from app.cin_technical_analysis import analyze_ohlc
except ModuleNotFoundError:
    from cin_technical_analysis import analyze_ohlc

router = APIRouter(tags=["technical-analysis"])


class OHLCBar(BaseModel):
    model_config = ConfigDict(extra="forbid")
    open: float = Field(gt=0, allow_inf_nan=False)
    high: float = Field(gt=0, allow_inf_nan=False)
    low: float = Field(gt=0, allow_inf_nan=False)
    close: float = Field(gt=0, allow_inf_nan=False)
    volume: float | None = Field(default=None, ge=0, allow_inf_nan=False)


class TechnicalAnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    symbol: str = Field(min_length=1, max_length=20, pattern=r"^[A-Za-z0-9._-]+$")
    timeframe: str = Field(default="unspecified", min_length=1, max_length=20, pattern=r"^[A-Za-z0-9._-]+$")
    candles: list[OHLCBar] = Field(min_length=5, max_length=500)


@router.post("/technical-analysis")
def technical_analysis(request: TechnicalAnalysisRequest) -> dict[str, Any]:
    """Analyze supplied OHLC candles only; no provider calls or trade execution."""
    try:
        result = analyze_ohlc([bar.model_dump() for bar in request.candles])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    result["input"]["symbol"] = request.symbol.upper()
    result["input"]["timeframe"] = request.timeframe
    return result
