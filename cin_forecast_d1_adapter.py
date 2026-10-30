"""HTTP adapter for the allowlisted CIN Cloudflare D1 Worker API.

No Cloudflare account API token is used here. The Worker service token is a
separate secret and must be configured only after a non-production deployment
has been explicitly approved.
"""
from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from typing import Any


class ForecastD1Error(RuntimeError):
    """A configured forecast storage gateway rejected or failed a request."""


def _call(operation: str, payload: dict[str, Any]) -> Any:
    base = os.getenv("CIN_FORECAST_D1_WORKER_URL", "").strip().rstrip("/")
    token = os.getenv("CIN_FORECAST_D1_WORKER_TOKEN", "")
    if not base or not token:
        raise ForecastD1Error("D1 forecast storage is not configured")
    if not base.startswith("https://"):
        raise ForecastD1Error("D1 Worker URL must use HTTPS")
    body = json.dumps({"operation": operation, "payload": payload},
                      separators=(",", ":"), allow_nan=False).encode("utf-8")
    request = Request(base + "/v1/ledger", data=body, method="POST", headers={
        "Authorization": "Bearer " + token,
        "Content-Type": "application/json",
        "Accept": "application/json",
    })
    try:
        with urlopen(request, timeout=10) as response:
            decoded = json.loads(response.read(131073))
    except HTTPError as exc:
        detail = exc.read(4096).decode("utf-8", "replace")
        raise ForecastD1Error(f"D1 Worker returned HTTP {exc.code}: {detail}") from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise ForecastD1Error("D1 Worker request failed") from exc
    if not isinstance(decoded, dict) or "result" not in decoded:
        raise ForecastD1Error("D1 Worker returned an invalid response")
    return decoded["result"]


def record_forecast(_database_path, forecast, *, recorded_at):
    return _call("create_forecast", {"forecast": dict(forecast),
                                     "recorded_at": recorded_at.isoformat() if hasattr(recorded_at, "isoformat") else recorded_at})


def record_forecast_observation(_database_path, observation):
    return _call("insert_observation", {"observation": dict(observation)})


def get_forecast(_database_path, forecast_id):
    return _call("get_forecast", {"forecast_id": forecast_id})


def get_forecast_evaluation(_database_path, forecast_id):
    return _call("get_evaluation", {"forecast_id": forecast_id})


def list_forecasts(_database_path, *, asset_id=None, limit=100):
    return _call("list_forecasts", {"asset_id": asset_id, "limit": limit})


def list_forecast_evaluations(_database_path, *, asset_id=None, limit=100):
    return _call("list_evaluations", {"asset_id": asset_id, "limit": limit})


def evaluate_and_record_forecast(_database_path, forecast_id, *, evaluated_at,
                                 max_observation_lag_seconds=3600):
    return _call("evaluate_forecast", {
        "forecast_id": forecast_id,
        "evaluated_at": evaluated_at.isoformat() if hasattr(evaluated_at, "isoformat") else evaluated_at,
        "max_observation_lag_seconds": max_observation_lag_seconds,
    })
