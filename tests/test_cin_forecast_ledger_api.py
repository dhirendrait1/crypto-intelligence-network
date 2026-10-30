"""Route-level security and behavior tests for the CIN forecast API."""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cin_forecast_ledger_api import router


def client(tmp_path, monkeypatch, *, token="test-write-token"):
    monkeypatch.setenv("CIN_FORECAST_DB_PATH", str(tmp_path / "forecast.sqlite3"))
    if token is None:
        monkeypatch.delenv("CIN_FORECAST_WRITE_TOKEN", raising=False)
    else:
        monkeypatch.setenv("CIN_FORECAST_WRITE_TOKEN", token)
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def auth(token="test-write-token"):
    return {"Authorization": f"Bearer {token}"}


FORECAST = {
    "forecast_id": "fc-btc-1",
    "asset_id": "BTC-USD",
    "metric": "price",
    "value": 70000,
    "unit": "USD",
    "source_id": "cin-model-v1",
    "created_at": "2026-10-30T10:00:00+00:00",
    "target_at": "2026-10-30T11:00:00+00:00",
    "invalidation_conditions": {"below": 68000},
}
OBSERVATION = {
    "observation_id": "obs-btc-1",
    "asset_id": "BTC-USD",
    "metric": "price",
    "value": 69500,
    "unit": "USD",
    "source_id": "coinbase-public",
    "observed_at": "2026-10-30T11:02:00Z",
    "retrieved_at": "2026-10-30T11:02:05Z",
}


def test_write_routes_require_bearer_token(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    assert c.post("/forecasts", json=FORECAST).status_code == 401
    assert c.post("/forecasts", json=FORECAST, headers=auth("wrong")).status_code == 401
    assert c.post("/forecasts", json=FORECAST, headers=auth()).status_code == 201


def test_write_routes_fail_closed_when_token_not_configured(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch, token=None)
    response = c.post("/forecasts", json=FORECAST)
    assert response.status_code == 503
    assert "write access is disabled" in response.json()["detail"]


def test_forecast_observation_evaluation_and_history_flow(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    headers = auth()
    assert c.post("/forecasts", json=FORECAST, headers=headers).status_code == 201
    observation = c.post("/forecasts/observations", json=OBSERVATION, headers=headers)
    assert observation.status_code == 201
    evaluation = c.post(
        "/forecasts/fc-btc-1/evaluate",
        json={"evaluated_at": "2026-10-30T12:00:00Z"},
        headers=headers,
    )
    assert evaluation.status_code == 200
    assert evaluation.json()["status"] == "evaluated"
    assert evaluation.json()["error"] == -500

    detail = c.get("/forecasts/fc-btc-1")
    assert detail.status_code == 200
    assert detail.json()["forecast"]["forecast_id"] == "fc-btc-1"
    assert detail.json()["evaluation"]["observation_id"] == "obs-btc-1"
    history = c.get("/forecasts?asset_id=BTC-USD")
    assert history.status_code == 200
    assert history.json()["count"] == 1


def test_scorecards_group_by_metric_and_unit_independently(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    headers = auth()
    assert c.post("/forecasts", json=FORECAST, headers=headers).status_code == 201
    assert c.post("/forecasts/observations", json=OBSERVATION, headers=headers).status_code == 201
    assert c.post(
        "/forecasts/fc-btc-1/evaluate",
        json={"evaluated_at": "2026-10-30T12:00:00Z"},
        headers=headers,
    ).status_code == 200

    other = {**FORECAST, "forecast_id": "fc-btc-volume", "metric": "volume",
             "value": 100, "unit": "BTC"}
    actual = {**OBSERVATION, "observation_id": "obs-btc-volume", "metric": "volume",
              "value": 90, "unit": "BTC"}
    assert c.post("/forecasts", json=other, headers=headers).status_code == 201
    assert c.post("/forecasts/observations", json=actual, headers=headers).status_code == 201
    assert c.post(
        "/forecasts/fc-btc-volume/evaluate",
        json={"evaluated_at": "2026-10-30T12:00:00Z"},
        headers=headers,
    ).status_code == 200

    response = c.get("/forecasts/scorecards/summary")
    assert response.status_code == 200
    cards = response.json()["items"]
    assert {(row["metric"], row["unit"]) for row in cards} == {
        ("price", "USD"), ("volume", "BTC")
    }


def test_unconfigured_storage_fails_closed(tmp_path, monkeypatch):
    monkeypatch.delenv("CIN_FORECAST_DB_PATH", raising=False)
    monkeypatch.setenv("CIN_FORECAST_WRITE_TOKEN", "test-write-token")
    app = FastAPI()
    app.include_router(router)
    response = TestClient(app).get("/forecasts")
    assert response.status_code == 503
    assert "storage is not configured" in response.json()["detail"]


def test_extra_fields_are_rejected(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    invalid = {**FORECAST, "wallet_private_key": "must-never-be-accepted"}
    assert c.post("/forecasts", json=invalid, headers=auth()).status_code == 422


def test_api_normalizes_offset_timestamps_to_utc(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    offset_forecast = {
        **FORECAST,
        "created_at": "2026-10-30T13:00:00+03:00",
        "target_at": "2026-10-30T14:00:00+03:00",
    }
    response = c.post("/forecasts", json=offset_forecast, headers=auth())
    assert response.status_code == 201
    assert response.json()["created_at"] == "2026-10-30T10:00:00Z"
    assert response.json()["target_at"] == "2026-10-30T11:00:00Z"


def test_api_rejects_naive_timestamps(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    naive_forecast = {
        **FORECAST,
        "created_at": "2026-10-30T10:00:00",
    }
    response = c.post("/forecasts", json=naive_forecast, headers=auth())
    assert response.status_code == 422
    assert "timezone" in response.json()["detail"]
