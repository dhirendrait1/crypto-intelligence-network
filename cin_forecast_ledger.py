"""SQLite persistence for CIN forecasts, observations, and retrospective outcomes.

Read-only research data only. This module does not fetch provider data or execute trades.
SQLite deployment requires a persistent writable disk and a single-host writer model.
"""
from __future__ import annotations

import json
import math
import sqlite3
from datetime import datetime, timedelta, timezone
from contextlib import closing
from pathlib import Path
from typing import Any, Mapping

from cin_forecast_outcomes import evaluate_forecast_outcome

_SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS cin_forecasts (
 forecast_id TEXT PRIMARY KEY, asset_id TEXT NOT NULL, metric TEXT NOT NULL,
 value REAL NOT NULL, unit TEXT NOT NULL, source_id TEXT NOT NULL,
 created_at TEXT NOT NULL, target_at TEXT NOT NULL,
 invalidation_conditions_json TEXT NOT NULL, recorded_at TEXT NOT NULL,
 payload_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cin_forecasts_asset_target ON cin_forecasts(asset_id,target_at);
CREATE TABLE IF NOT EXISTS cin_forecast_observations (
 observation_id TEXT PRIMARY KEY, asset_id TEXT NOT NULL, metric TEXT NOT NULL,
 value REAL NOT NULL, unit TEXT NOT NULL, source_id TEXT NOT NULL,
 observed_at TEXT NOT NULL, retrieved_at TEXT NOT NULL, payload_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cin_forecast_observations_match
 ON cin_forecast_observations(asset_id,metric,unit,observed_at);
CREATE TABLE IF NOT EXISTS cin_forecast_evaluations (
 forecast_id TEXT PRIMARY KEY REFERENCES cin_forecasts(forecast_id),
 observation_id TEXT NOT NULL REFERENCES cin_forecast_observations(observation_id),
 evaluated_at TEXT NOT NULL, result_json TEXT NOT NULL
);
"""

def _time(value: Any, field: str) -> datetime:
    if isinstance(value, str):
        try: value = datetime.fromisoformat(value.replace("Z","+00:00"))
        except (TypeError,ValueError,OverflowError) as exc: raise ValueError(f"{field} must be ISO-8601") from exc
    if not isinstance(value,datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must include an explicit timezone")
    return value.astimezone(timezone.utc)

def _text(value: Any, field: str, maximum: int=160) -> str:
    if not isinstance(value,str) or not value.strip() or len(value)>maximum or any(ord(c)<32 or ord(c)==127 for c in value):
        raise ValueError(f"{field} must be a non-empty sanitized string of at most {maximum} characters")
    return value.strip()

def _number(value: Any, field: str) -> float:
    if isinstance(value,bool) or not isinstance(value,(int,float)):
        raise ValueError(f"{field} must be a finite number")
    try:
        result=float(value)
    except (OverflowError,ValueError):
        raise ValueError(f"{field} must be a finite number")
    if not math.isfinite(result):
        raise ValueError(f"{field} must be a finite number")
    return result

def _json(value: Any, field: str) -> str:
    try: return json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False)
    except (TypeError,ValueError) as exc: raise ValueError(f"{field} must be finite JSON data") from exc

def _connect(path: str | Path) -> sqlite3.Connection:
    if str(path)==":memory:": raise ValueError("persistent SQLite file path required")
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(str(path),timeout=10,isolation_level=None)
    db.execute("PRAGMA busy_timeout=10000")
    db.execute("PRAGMA foreign_keys=ON")
    db.executescript(_SCHEMA)
    return db

def _forecast_payload(f: Mapping[str,Any], recorded_at: str) -> dict[str,Any]:
    if not isinstance(f,Mapping): raise ValueError("forecast must be a mapping")
    result={
      "forecast_id":_text(f.get("forecast_id"),"forecast_id"),
      "asset_id":_text(f.get("asset_id"),"asset_id"),
      "metric":_text(f.get("metric"),"metric"),
      "value":_number(f.get("value"),"forecast.value"),
      "unit":_text(f.get("unit"),"forecast.unit",40),
      "source_id":_text(f.get("source_id"),"forecast.source_id"),
      "created_at":_time(f.get("created_at"),"forecast.created_at").isoformat(),
      "target_at":_time(f.get("target_at"),"forecast.target_at").isoformat(),
      "invalidation_conditions":f.get("invalidation_conditions",{}),
      "recorded_at":recorded_at,
    }
    if result["target_at"]<=result["created_at"]: raise ValueError("target_at must be later than created_at")
    _json(result["invalidation_conditions"],"invalidation_conditions")
    return result

def record_forecast(database_path: str | Path, forecast: Mapping[str,Any], *, recorded_at: datetime | str) -> dict[str,Any]:
    """Insert a forecast once. Repeated identical IDs are idempotent; conflicting reuse fails."""
    item=_forecast_payload(forecast,_time(recorded_at,"recorded_at").isoformat())
    encoded=_json(item,"forecast")
    with closing(_connect(database_path)) as db:
        db.execute("BEGIN IMMEDIATE")
        try:
            old=db.execute("SELECT payload_json FROM cin_forecasts WHERE forecast_id=?",(item["forecast_id"],)).fetchone()
            if old:
                existing=json.loads(old[0])
                comparable=dict(item)
                existing.pop("recorded_at",None)
                comparable.pop("recorded_at",None)
                if existing!=comparable: raise ValueError("forecast_id already exists with different content")
                item=json.loads(old[0])
            else:
                db.execute("""INSERT INTO cin_forecasts VALUES(?,?,?,?,?,?,?,?,?,?,?)""",(
                  item["forecast_id"],item["asset_id"],item["metric"],item["value"],item["unit"],
                  item["source_id"],item["created_at"],item["target_at"],
                  _json(item["invalidation_conditions"],"invalidation_conditions"),
                  item["recorded_at"],encoded))
            db.execute("COMMIT")
        except Exception:
            if db.in_transaction: db.execute("ROLLBACK")
            raise
    return item

def record_forecast_observation(database_path: str | Path, observation: Mapping[str,Any]) -> dict[str,Any]:
    """Persist immutable source observation identity and both event/retrieval timestamps."""
    if not isinstance(observation,Mapping): raise ValueError("observation must be a mapping")
    item={
      "observation_id":_text(observation.get("observation_id"),"observation_id"),
      "asset_id":_text(observation.get("asset_id"),"observation.asset_id"),
      "metric":_text(observation.get("metric"),"observation.metric"),
      "value":_number(observation.get("value"),"observation.value"),
      "unit":_text(observation.get("unit"),"observation.unit",40),
      "source_id":_text(observation.get("source_id"),"observation.source_id"),
      "observed_at":_time(observation.get("observed_at"),"observed_at").isoformat(),
      "retrieved_at":_time(observation.get("retrieved_at"),"retrieved_at").isoformat(),
    }
    if item["retrieved_at"]<item["observed_at"]: raise ValueError("retrieved_at cannot precede observed_at")
    encoded=_json(item,"observation")
    with closing(_connect(database_path)) as db:
        db.execute("BEGIN IMMEDIATE")
        try:
            old=db.execute("SELECT payload_json FROM cin_forecast_observations WHERE observation_id=?",(item["observation_id"],)).fetchone()
            if old and old[0]!=encoded: raise ValueError("observation_id already exists with different content")
            if not old:
                db.execute("INSERT INTO cin_forecast_observations VALUES(?,?,?,?,?,?,?,?,?)",(
                  item["observation_id"],item["asset_id"],item["metric"],item["value"],item["unit"],
                  item["source_id"],item["observed_at"],item["retrieved_at"],encoded))
            db.execute("COMMIT")
        except Exception:
            if db.in_transaction: db.execute("ROLLBACK")
            raise
    return item

def get_forecast(database_path: str | Path, forecast_id: str) -> dict[str,Any] | None:
    key=_text(forecast_id,"forecast_id")
    with closing(_connect(database_path)) as db:
        row=db.execute("SELECT payload_json FROM cin_forecasts WHERE forecast_id=?",(key,)).fetchone()
    return json.loads(row[0]) if row else None

def list_forecasts(database_path: str | Path, *, asset_id: str | None=None, limit: int=100) -> list[dict[str,Any]]:
    if isinstance(limit,bool) or not isinstance(limit,int) or not 1<=limit<=500: raise ValueError("limit must be 1..500")
    sql="SELECT payload_json FROM cin_forecasts"
    args: tuple[Any,...]=()
    if asset_id is not None: sql+=" WHERE asset_id=?"; args=(_text(asset_id,"asset_id"),)
    sql+=" ORDER BY created_at DESC,forecast_id LIMIT ?"; args+=(limit,)
    with closing(_connect(database_path)) as db: rows=db.execute(sql,args).fetchall()
    return [json.loads(r[0]) for r in rows]

def evaluate_and_record_forecast(
    database_path: str | Path, forecast_id: str, *, evaluated_at: datetime | str,
    max_observation_lag_seconds: int=3600,
) -> dict[str,Any]:
    """Evaluate once against the nearest matching observation in [target, target+tolerance]."""
    key=_text(forecast_id,"forecast_id")
    if isinstance(max_observation_lag_seconds,bool) or not isinstance(max_observation_lag_seconds,int) or not 0<=max_observation_lag_seconds<=604800:
        raise ValueError("max_observation_lag_seconds must be an integer from 0 through 604800")
    now=_time(evaluated_at,"evaluated_at")
    with closing(_connect(database_path)) as db:
        db.execute("BEGIN IMMEDIATE")
        try:
            prior=db.execute("SELECT result_json FROM cin_forecast_evaluations WHERE forecast_id=?",(key,)).fetchone()
            if prior:
                result=json.loads(prior[0]); db.execute("COMMIT"); return result
            row=db.execute("SELECT payload_json FROM cin_forecasts WHERE forecast_id=?",(key,)).fetchone()
            if not row: raise ValueError("forecast_id not found")
            f=json.loads(row[0]); target=_time(f["target_at"],"target_at")
            if now<target: raise ValueError("forecast horizon has not closed")
            cutoff=(target+timedelta(seconds=max_observation_lag_seconds)).isoformat()
            obs=db.execute("""SELECT payload_json FROM cin_forecast_observations
              WHERE asset_id=? AND metric=? AND unit=? AND observed_at>=? AND observed_at<=?
              ORDER BY ABS(julianday(observed_at)-julianday(?)),observed_at,observation_id LIMIT 1""",
              (f["asset_id"],f["metric"],f["unit"],target.isoformat(),cutoff,target.isoformat())).fetchone()
            if not obs:
                result={"forecast_id":key,"status":"not_evaluable","reason":"no_matching_observation_within_horizon_tolerance",
                        "target_at":target.isoformat(),"max_observation_lag_seconds":max_observation_lag_seconds}
                db.execute("COMMIT"); return result
            actual=json.loads(obs[0])
            result=evaluate_forecast_outcome(f,{
              "observation_id":actual["observation_id"],"metric":actual["metric"],"value":actual["value"],
              "unit":actual["unit"],"observed_at":actual["observed_at"],"source_id":actual["source_id"]})
            if result.get("status")=="evaluated":
                result["asset_id"]=f["asset_id"]
                result["observation_retrieved_at"]=actual["retrieved_at"]
                result["max_observation_lag_seconds"]=max_observation_lag_seconds
                db.execute("INSERT INTO cin_forecast_evaluations VALUES(?,?,?,?)",(
                  key,actual["observation_id"],now.isoformat(),_json(result,"evaluation")))
            db.execute("COMMIT"); return result
        except Exception:
            if db.in_transaction: db.execute("ROLLBACK")
            raise

def get_forecast_evaluation(database_path: str | Path, forecast_id: str) -> dict[str,Any] | None:
    key=_text(forecast_id,"forecast_id")
    with closing(_connect(database_path)) as db:
        row=db.execute("SELECT result_json FROM cin_forecast_evaluations WHERE forecast_id=?",(key,)).fetchone()
    return json.loads(row[0]) if row else None

def list_forecast_evaluations(database_path: str | Path, *, asset_id: str | None=None, limit: int=100) -> list[dict[str,Any]]:
    if isinstance(limit,bool) or not isinstance(limit,int) or not 1<=limit<=500: raise ValueError("limit must be 1..500")
    sql="""SELECT e.result_json FROM cin_forecast_evaluations e
      JOIN cin_forecasts f ON f.forecast_id=e.forecast_id"""
    args: tuple[Any,...]=()
    if asset_id is not None: sql+=" WHERE f.asset_id=?"; args=(_text(asset_id,"asset_id"),)
    sql+=" ORDER BY e.evaluated_at DESC,e.forecast_id LIMIT ?"; args+=(limit,)
    with closing(_connect(database_path)) as db: rows=db.execute(sql,args).fetchall()
    return [json.loads(r[0]) for r in rows]

def initialize_forecast_ledger(database_path: str | Path) -> None:
    """Create/validate the ledger schema during application startup."""
    with closing(_connect(database_path)) as db:
        result = db.execute("PRAGMA quick_check").fetchone()
        if not result or result[0] != "ok":
            raise RuntimeError("CIN forecast ledger SQLite integrity check failed")

