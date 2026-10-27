"""Append-only forecast ledger and post-horizon outcome evaluation for CIN.

This module is research-only. It never places trades or emits investment advice.
Only observations at or after a forecast's horizon are eligible for evaluation.
"""
from __future__ import annotations

import json
import math
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping


_SCHEMA = """
CREATE TABLE IF NOT EXISTS cin_forecasts (
    forecast_id TEXT PRIMARY KEY,
    asset TEXT NOT NULL,
    source TEXT NOT NULL,
    issued_at TEXT NOT NULL,
    horizon_seconds INTEGER NOT NULL CHECK(horizon_seconds > 0),
    target_at TEXT NOT NULL,
    reference_price REAL NOT NULL,
    target_price REAL NOT NULL,
    direction TEXT NOT NULL CHECK(direction IN ('up','down')),
    invalidation_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS cin_forecast_outcomes (
    forecast_id TEXT PRIMARY KEY REFERENCES cin_forecasts(forecast_id),
    evaluated_at TEXT NOT NULL,
    observation_source TEXT NOT NULL,
    observation_at TEXT NOT NULL,
    observed_price REAL NOT NULL,
    direction_correct INTEGER NOT NULL CHECK(direction_correct IN (0,1)),
    absolute_error REAL NOT NULL,
    percentage_error REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cin_forecasts_target ON cin_forecasts(target_at);
"""


def _time(value: datetime | str, field: str) -> datetime:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"{field} must be an ISO-8601 timestamp") from exc
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must include an explicit timezone")
    return value.astimezone(timezone.utc)


def _price(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a finite positive number")
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"{field} must be a finite positive number")
    return number


def _connect(path: str | Path) -> sqlite3.Connection:
    target = str(path)
    if target == ":memory:":
        raise ValueError("a persistent SQLite file path is required")
    Path(target).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(target, timeout=10, isolation_level=None)
    db.execute("PRAGMA busy_timeout=10000")
    db.execute("PRAGMA foreign_keys=ON")
    db.executescript(_SCHEMA)
    return db


def record_forecast(
    database_path: str | Path,
    *,
    forecast_id: str,
    asset: str,
    source: str,
    issued_at: datetime | str,
    horizon_seconds: int,
    reference_price: float,
    target_price: float,
    direction: str,
    invalidation_conditions: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Persist an immutable forecast and its explicit target timestamp."""
    for field, value, maximum in (
        ("forecast_id", forecast_id, 160), ("asset", asset, 40), ("source", source, 160)
    ):
        if not isinstance(value, str) or not value.strip() or len(value) > maximum:
            raise ValueError(f"{field} must be a non-empty string of at most {maximum} characters")
    if isinstance(horizon_seconds, bool) or not isinstance(horizon_seconds, int) or not 60 <= horizon_seconds <= 31_536_000:
        raise ValueError("horizon_seconds must be an integer from 60 through 31536000")
    if direction not in ("up", "down"):
        raise ValueError("direction must be 'up' or 'down'")
    issued = _time(issued_at, "issued_at")
    reference = _price(reference_price, "reference_price")
    target = _price(target_price, "target_price")
    if (direction == "up" and target <= reference) or (direction == "down" and target >= reference):
        raise ValueError("target_price must be above reference for 'up' and below for 'down'")
    conditions = {} if invalidation_conditions is None else invalidation_conditions
    if not isinstance(conditions, Mapping):
        raise ValueError("invalidation_conditions must be a mapping")
    try:
        conditions_json = json.dumps(dict(conditions), sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("invalidation_conditions must be JSON-serializable without non-finite numbers") from exc
    target_at = (issued + timedelta(seconds=horizon_seconds)).isoformat()
    created_at = datetime.now(timezone.utc).isoformat()
    with _connect(database_path) as db:
        db.execute("BEGIN IMMEDIATE")
        try:
            db.execute(
                """INSERT INTO cin_forecasts
                (forecast_id,asset,source,issued_at,horizon_seconds,target_at,reference_price,
                 target_price,direction,invalidation_json,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (forecast_id, asset.strip().upper(), source.strip(), issued.isoformat(), horizon_seconds,
                 target_at, reference, target, direction, conditions_json, created_at),
            )
            db.execute("COMMIT")
        except Exception:
            if db.in_transaction:
                db.execute("ROLLBACK")
            raise
    return {
        "forecast_id": forecast_id, "asset": asset.strip().upper(), "source": source.strip(),
        "issued_at": issued.isoformat(), "horizon_seconds": horizon_seconds, "target_at": target_at,
        "reference_price": reference, "target_price": target, "direction": direction,
        "invalidation_conditions": dict(conditions), "status": "pending_outcome",
    }


def evaluate_forecast_outcome(
    database_path: str | Path,
    *,
    forecast_id: str,
    observation_source: str,
    observation_at: datetime | str,
    observed_price: float,
    evaluated_at: datetime | str,
) -> dict[str, Any]:
    """Score a forecast only after its target time using a timestamped observation."""
    if not isinstance(forecast_id, str) or not forecast_id.strip():
        raise ValueError("forecast_id must be a non-empty string")
    if not isinstance(observation_source, str) or not observation_source.strip() or len(observation_source) > 160:
        raise ValueError("observation_source must be a non-empty string of at most 160 characters")
    observed_time = _time(observation_at, "observation_at")
    evaluated_time = _time(evaluated_at, "evaluated_at")
    price = _price(observed_price, "observed_price")
    if observed_time > evaluated_time:
        raise ValueError("observation_at cannot be in the future relative to evaluated_at")
    with _connect(database_path) as db:
        db.execute("BEGIN IMMEDIATE")
        try:
            forecast = db.execute(
                """SELECT asset,source,issued_at,horizon_seconds,target_at,reference_price,
                          target_price,direction FROM cin_forecasts WHERE forecast_id=?""",
                (forecast_id,),
            ).fetchone()
            if forecast is None:
                raise ValueError("forecast_id not found")
            asset, source, issued, horizon, target_at, reference, target, direction = forecast
            if observed_time < _time(target_at, "target_at"):
                raise ValueError("outcome observation must be at or after forecast target_at")
            if evaluated_time < _time(target_at, "target_at"):
                raise ValueError("forecast horizon has not elapsed")
            if observed_time < _time(issued, "issued_at"):
                raise ValueError("observation cannot predate forecast issuance")
            if source.strip().lower() == observation_source.strip().lower():
                # Same source can be valid, but provenance is still recorded. No silent substitution.
                pass
            correct = (price >= target) if direction == "up" else (price <= target)
            absolute_error = abs(price - target)
            percentage_error = absolute_error / target * 100.0
            db.execute(
                """INSERT INTO cin_forecast_outcomes
                (forecast_id,evaluated_at,observation_source,observation_at,observed_price,
                 direction_correct,absolute_error,percentage_error)
                VALUES (?,?,?,?,?,?,?,?)""",
                (forecast_id, evaluated_time.isoformat(), observation_source.strip(),
                 observed_time.isoformat(), price, int(correct), absolute_error, percentage_error),
            )
            db.execute("COMMIT")
        except Exception:
            if db.in_transaction:
                db.execute("ROLLBACK")
            raise
    return {
        "forecast_id": forecast_id, "asset": asset, "forecast_source": source,
        "observation_source": observation_source.strip(), "target_at": target_at,
        "observation_at": observed_time.isoformat(), "evaluated_at": evaluated_time.isoformat(),
        "target_price": target, "observed_price": price, "direction": direction,
        "direction_correct": bool(correct), "absolute_error": absolute_error,
        "percentage_error": percentage_error, "status": "evaluated",
        "note": "Single-observation outcome score; not a calibrated probability or trading recommendation.",
    }


def forecast_calibration_summary(database_path: str | Path) -> dict[str, Any]:
    """Return descriptive aggregate scores; never imply calibration from sparse samples."""
    with _connect(database_path) as db:
        forecasts = db.execute("SELECT COUNT(*) FROM cin_forecasts").fetchone()[0]
        rows = db.execute(
            """SELECT COUNT(*), COALESCE(SUM(direction_correct),0),
                      COALESCE(AVG(absolute_error),0), COALESCE(AVG(percentage_error),0)
               FROM cin_forecast_outcomes"""
        ).fetchone()
    evaluated, correct, mean_abs, mean_pct = rows
    return {
        "forecast_count": forecasts, "evaluated_count": evaluated,
        "pending_outcome_count": forecasts - evaluated,
        "directional_accuracy": (correct / evaluated) if evaluated else None,
        "mean_absolute_price_error": float(mean_abs) if evaluated else None,
        "mean_absolute_percentage_error": float(mean_pct) if evaluated else None,
        "status": "descriptive_only" if evaluated else "no_evaluated_forecasts",
        "limitations": [
            "Outcome scores use one eligible observation at or after each horizon.",
            "Directional accuracy and price error do not establish probability calibration.",
            "Source coverage, missing observations, survivorship bias, and look-ahead controls need separate review.",
        ],
    }
