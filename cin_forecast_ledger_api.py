"""FastAPI endpoints for the retrospective CIN forecast ledger.

Read endpoints expose recorded research evidence. Mutating endpoints require a
server-side CIN_FORECAST_WRITE_TOKEN and bearer authentication. No market orders,
wallet operations, or fund movement are implemented here.
"""
from __future__ import annotations

import hmac
from contextlib import asynccontextmanager
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field

try:
    from app.cin_forecast_ledger import (
        evaluate_and_record_forecast,
        get_forecast,
        get_forecast_evaluation,
        initialize_forecast_ledger,
        list_forecast_evaluations,
        list_forecasts,
        record_forecast,
        record_forecast_observation,
    )
except ModuleNotFoundError as exc:
    if exc.name not in {"app", "app.cin_forecast_ledger"}:
        raise
    from cin_forecast_ledger import (
        evaluate_and_record_forecast,
        get_forecast,
        get_forecast_evaluation,
        initialize_forecast_ledger,
        list_forecast_evaluations,
        list_forecasts,
        record_forecast,
        record_forecast_observation,
    )

@asynccontextmanager
async def _forecast_lifespan(app):
    """Initialize configured SQLite schema before serving forecast requests."""
    d1_url = os.getenv("CIN_FORECAST_D1_WORKER_URL", "").strip()
    d1_token = os.getenv("CIN_FORECAST_D1_WORKER_TOKEN", "")
    raw = os.getenv("CIN_FORECAST_DB_PATH", "").strip()
    if d1_url or d1_token:
        if not d1_url.startswith("https://") or not d1_token:
            raise RuntimeError("Both HTTPS D1 Worker URL and D1 Worker token must be configured")
    elif raw:
        path = Path(raw)
        if not path.is_absolute():
            raise RuntimeError("CIN_FORECAST_DB_PATH must be an absolute path")
        initialize_forecast_ledger(path)
    yield


router = APIRouter(prefix="/forecasts", tags=["forecast ledger"], lifespan=_forecast_lifespan)
_bearer = HTTPBearer(auto_error=False)


def _database_path() -> Path:
    d1_url = os.getenv("CIN_FORECAST_D1_WORKER_URL", "").strip()
    d1_token = os.getenv("CIN_FORECAST_D1_WORKER_TOKEN", "")
    if d1_url or d1_token:
        if not d1_url.startswith("https://") or not d1_token:
            raise HTTPException(status_code=503, detail="D1 Worker URL and token must both be configured")
        return Path("/__cin_d1_remote__")
    raw = os.getenv("CIN_FORECAST_DB_PATH", "").strip()
    if not raw:
        raise HTTPException(
            status_code=503,
            detail="Forecast storage is not configured; set CIN_FORECAST_DB_PATH to a durable writable path",
        )
    path = Path(raw)
    if not path.is_absolute():
        raise HTTPException(status_code=503, detail="CIN_FORECAST_DB_PATH must be an absolute path")
    return path


def _require_write_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> None:
    expected = os.getenv("CIN_FORECAST_WRITE_TOKEN", "")
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Forecast write access is disabled until CIN_FORECAST_WRITE_TOKEN is configured",
        )
    if credentials is None or credentials.scheme.lower() != "bearer" or not hmac.compare_digest(
        credentials.credentials, expected
    ):
        raise HTTPException(status_code=401, detail="Valid bearer token required")


class ForecastInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    forecast_id: str = Field(min_length=1, max_length=160)
    asset_id: str = Field(min_length=1, max_length=160)
    metric: str = Field(min_length=1, max_length=160)
    value: float
    unit: str = Field(min_length=1, max_length=40)
    source_id: str = Field(min_length=1, max_length=160)
    created_at: datetime
    target_at: datetime
    invalidation_conditions: dict[str, Any] = Field(default_factory=dict)


class ObservationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    observation_id: str = Field(min_length=1, max_length=160)
    asset_id: str = Field(min_length=1, max_length=160)
    metric: str = Field(min_length=1, max_length=160)
    value: float
    unit: str = Field(min_length=1, max_length=40)
    source_id: str = Field(min_length=1, max_length=160)
    observed_at: datetime
    retrieved_at: datetime


class EvaluationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evaluated_at: datetime | None = None
    max_observation_lag_seconds: int = Field(default=3600, ge=0, le=604800)


def _payload(model: BaseModel) -> dict[str, Any]:
    """Serialize API timestamps as UTC for chronological D1 ISO-text comparisons."""
    payload = model.model_dump(mode="python")
    for key, value in payload.items():
        if isinstance(value, datetime):
            if value.tzinfo is None or value.utcoffset() is None:
                raise HTTPException(status_code=422, detail=f"{key} must include a timezone")
            payload[key] = value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return payload


def _translate_value_error(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _ledger_call(fn, *args, **kwargs):
    """Select remote D1 adapter only when its complete HTTPS configuration exists."""
    d1_url = os.getenv("CIN_FORECAST_D1_WORKER_URL", "").strip()
    d1_token = os.getenv("CIN_FORECAST_D1_WORKER_TOKEN", "")
    try:
        if d1_url or d1_token:
            if not d1_url.startswith("https://") or not d1_token:
                raise HTTPException(status_code=503, detail="D1 Worker URL and token must both be configured")
            try:
                from app import cin_forecast_d1_adapter as adapter
            except ModuleNotFoundError:
                import cin_forecast_d1_adapter as adapter
            return getattr(adapter, fn.__name__)(*args, **kwargs)
        return fn(*args, **kwargs)
    except Exception as exc:
        if exc.__class__.__name__ == "ForecastD1Error":
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        if isinstance(exc, ValueError):
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        raise


@router.post("", status_code=201, dependencies=[Depends(_require_write_token)])
def create_forecast(request: ForecastInput) -> dict[str, Any]:
    return _ledger_call(
        record_forecast,
        _database_path(),
        _payload(request),
        recorded_at=datetime.now(timezone.utc),
    )


@router.get("")
def forecast_history(
    asset_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    rows = _ledger_call(list_forecasts, _database_path(), asset_id=asset_id, limit=limit)
    return {"count": len(rows), "items": rows, "read_only": True}


@router.get("/{forecast_id}")
def forecast_detail(forecast_id: str) -> dict[str, Any]:
    item = _ledger_call(get_forecast, _database_path(), forecast_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Forecast not found")
    return {"forecast": item, "evaluation": _ledger_call(get_forecast_evaluation, _database_path(), forecast_id),
            "read_only": True}


@router.post("/observations", status_code=201, dependencies=[Depends(_require_write_token)])
def ingest_observation(request: ObservationInput) -> dict[str, Any]:
    item = _ledger_call(record_forecast_observation, _database_path(), _payload(request))
    return {"observation": item, "read_only": True}


@router.post("/{forecast_id}/evaluate", dependencies=[Depends(_require_write_token)])
def evaluate_forecast(forecast_id: str, request: EvaluationInput) -> dict[str, Any]:
    evaluated_at = request.evaluated_at or datetime.now(timezone.utc)
    result = _ledger_call(
        evaluate_and_record_forecast,
        _database_path(),
        forecast_id,
        evaluated_at=evaluated_at,
        max_observation_lag_seconds=request.max_observation_lag_seconds,
    )
    return result


@router.get("/scorecards/summary")
def forecast_scorecards(
    asset_id: str | None = None,
    limit: int = Query(default=500, ge=1, le=500),
) -> dict[str, Any]:
    """Compute independent descriptive scorecards per asset, metric and unit."""
    rows = _ledger_call(
        list_forecast_evaluations, _database_path(), asset_id=asset_id, limit=limit
    )
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("status") != "evaluated":
            continue
        key = (str(row.get("asset_id", "")), str(row.get("metric", "")), str(row.get("unit", "")))
        if all(key):
            groups[key].append(row)

    cards = []
    for (asset, metric, unit), items in sorted(groups.items()):
        errors = [float(item["error"]) for item in items]
        absolute = [abs(value) for value in errors]
        squared = [value * value for value in errors]
        percentages = [
            float(item["absolute_percentage_error"])
            for item in items
            if item.get("absolute_percentage_error") is not None
        ]
        n = len(items)
        cards.append({
            "asset_id": asset,
            "metric": metric,
            "unit": unit,
            "evaluated_count": n,
            "mean_error": sum(errors) / n,
            "mean_absolute_error": sum(absolute) / n,
            "root_mean_squared_error": (sum(squared) / n) ** 0.5,
            "mean_absolute_percentage_error": (
                sum(percentages) / len(percentages) if percentages else None
            ),
            "mape_sample_count": len(percentages),
        })
    return {"count": len(cards), "items": cards, "read_only": True}
