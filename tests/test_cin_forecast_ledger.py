"""Offline regressions for persistent CIN forecast storage and evaluation."""
import sqlite3
import pytest
from cin_forecast_ledger import (
    record_forecast, record_forecast_observation, get_forecast, list_forecasts,
    evaluate_and_record_forecast, get_forecast_evaluation, list_forecast_evaluations,
)
NOW="2026-10-30T12:00:00Z"
F={"forecast_id":"fc-btc-1","asset_id":"BTC-USD","metric":"price","value":70000,
   "unit":"USD","source_id":"cin-model-v1","created_at":"2026-10-30T10:00:00Z",
   "target_at":"2026-10-30T11:00:00Z","invalidation_conditions":{"below":68000}}
O={"observation_id":"obs-btc-1","asset_id":"BTC-USD","metric":"price","value":69500,
   "unit":"USD","source_id":"coinbase-public","observed_at":"2026-10-30T11:02:00Z",
   "retrieved_at":"2026-10-30T11:02:05Z"}

def test_forecast_persists_and_reopens(tmp_path):
    p=tmp_path/"data"/"forecast.sqlite3"
    record_forecast(p,F,recorded_at=NOW)
    assert get_forecast(p,F["forecast_id"])["value"]==70000
    assert list_forecasts(p)[0]["source_id"]=="cin-model-v1"

def test_forecast_idempotency_and_conflict(tmp_path):
    p=tmp_path/"f.db"
    first=record_forecast(p,F,recorded_at=NOW)
    assert first==record_forecast(p,F,recorded_at="2026-10-30T12:05:00Z")
    with pytest.raises(ValueError,match="different content"):
        record_forecast(p,{**F,"value":71000},recorded_at=NOW)

def test_observation_provenance_and_idempotency(tmp_path):
    p=tmp_path/"f.db"
    assert record_forecast_observation(p,O)==record_forecast_observation(p,O)
    with pytest.raises(ValueError,match="different content"):
        record_forecast_observation(p,{**O,"value":69000})

def test_evaluation_uses_nearest_matching_observation(tmp_path):
    p=tmp_path/"f.db"; record_forecast(p,F,recorded_at=NOW)
    record_forecast_observation(p,{**O,"observation_id":"later","value":69000,
      "observed_at":"2026-10-30T11:20:00Z","retrieved_at":"2026-10-30T11:20:01Z"})
    record_forecast_observation(p,O)
    r=evaluate_and_record_forecast(p,F["forecast_id"],evaluated_at=NOW)
    assert r["status"]=="evaluated" and r["observation_id"]=="obs-btc-1"
    assert r["error"]==-500 and r["source_id"]=="coinbase-public"
    assert get_forecast_evaluation(p,F["forecast_id"])==r
    assert len(list_forecast_evaluations(p,asset_id="BTC-USD"))==1

def test_evaluation_is_immutable_and_idempotent(tmp_path):
    p=tmp_path/"f.db"; record_forecast(p,F,recorded_at=NOW); record_forecast_observation(p,O)
    first=evaluate_and_record_forecast(p,F["forecast_id"],evaluated_at=NOW)
    record_forecast_observation(p,{**O,"observation_id":"newer","value":70000,
      "observed_at":"2026-10-30T11:01:00Z","retrieved_at":"2026-10-30T11:01:01Z"})
    assert evaluate_and_record_forecast(p,F["forecast_id"],evaluated_at=NOW)==first

def test_mismatched_asset_and_outside_tolerance_are_not_evaluable(tmp_path):
    p=tmp_path/"f.db"; record_forecast(p,F,recorded_at=NOW)
    record_forecast_observation(p,{**O,"asset_id":"ETH-USD"})
    r=evaluate_and_record_forecast(p,F["forecast_id"],evaluated_at=NOW)
    assert r["status"]=="not_evaluable"
    p2=tmp_path/"f2.db"; record_forecast(p2,F,recorded_at=NOW)
    record_forecast_observation(p2,{**O,"observed_at":"2026-10-30T12:01:00Z",
      "retrieved_at":"2026-10-30T12:01:01Z"})
    r2=evaluate_and_record_forecast(p2,F["forecast_id"],evaluated_at=NOW,max_observation_lag_seconds=3600)
    assert r2["status"]=="not_evaluable"

def test_invalid_time_numeric_and_memory_path_rejected(tmp_path):
    with pytest.raises(ValueError,match="finite number"):
        record_forecast(tmp_path/"f.db",{**F,"value":float("nan")},recorded_at=NOW)
    with pytest.raises(ValueError,match="explicit timezone"):
        record_forecast(tmp_path/"f.db",{**F,"created_at":"2026-10-30T10:00:00"},recorded_at=NOW)
    with pytest.raises(ValueError,match="persistent SQLite"):
        record_forecast(":memory:",F,recorded_at=NOW)
    with pytest.raises(ValueError,match="horizon has not closed"):
        p=tmp_path/"future.db"; record_forecast(p,F,recorded_at=NOW)
        evaluate_and_record_forecast(p,F["forecast_id"],evaluated_at="2026-10-30T10:59:00Z")

def test_concurrent_duplicate_forecast_inserts_once(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    p=tmp_path/"f.db"
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda _:record_forecast(p,F,recorded_at=NOW),range(4)))
    with sqlite3.connect(p) as db:
        assert db.execute("SELECT COUNT(*) FROM cin_forecasts").fetchone()[0]==1
