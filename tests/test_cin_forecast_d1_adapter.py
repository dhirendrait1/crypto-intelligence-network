"""Offline contract tests for the CIN D1 Worker HTTP adapter."""
import json
from io import BytesIO

import pytest

import cin_forecast_d1_adapter as adapter


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self, limit=-1):
        return self.payload[:limit]


def test_adapter_sends_typed_operation_and_bearer(monkeypatch):
    monkeypatch.setenv("CIN_FORECAST_D1_WORKER_URL", "https://cin-ledger.example.workers.dev")
    monkeypatch.setenv("CIN_FORECAST_D1_WORKER_TOKEN", "service-secret")
    seen = {}
    def fake_urlopen(request, timeout):
        seen["url"] = request.full_url
        seen["auth"] = request.get_header("Authorization")
        seen["timeout"] = timeout
        seen["body"] = json.loads(request.data)
        return FakeResponse(b'{"result":{"forecast_id":"fc-1"}}')
    monkeypatch.setattr(adapter, "urlopen", fake_urlopen)

    result = adapter.get_forecast(None, "fc-1")

    assert result == {"forecast_id": "fc-1"}
    assert seen["url"] == "https://cin-ledger.example.workers.dev/v1/ledger"
    assert seen["auth"] == "Bearer service-secret"
    assert seen["timeout"] == 10
    assert seen["body"] == {"operation": "get_forecast", "payload": {"forecast_id": "fc-1"}}


def test_adapter_requires_https_and_both_settings(monkeypatch):
    monkeypatch.setenv("CIN_FORECAST_D1_WORKER_URL", "http://not-secure.example")
    monkeypatch.setenv("CIN_FORECAST_D1_WORKER_TOKEN", "secret")
    with pytest.raises(adapter.ForecastD1Error, match="HTTPS"):
        adapter.get_forecast(None, "fc-1")
    monkeypatch.setenv("CIN_FORECAST_D1_WORKER_URL", "https://secure.example")
    monkeypatch.delenv("CIN_FORECAST_D1_WORKER_TOKEN", raising=False)
    with pytest.raises(adapter.ForecastD1Error, match="not configured"):
        adapter.get_forecast(None, "fc-1")


def test_adapter_rejects_invalid_worker_response(monkeypatch):
    monkeypatch.setenv("CIN_FORECAST_D1_WORKER_URL", "https://cin-ledger.example.workers.dev")
    monkeypatch.setenv("CIN_FORECAST_D1_WORKER_TOKEN", "secret")
    monkeypatch.setattr(adapter, "urlopen", lambda *a, **k: FakeResponse(b'{"unexpected":true}'))
    with pytest.raises(adapter.ForecastD1Error, match="invalid response"):
        adapter.get_forecast(None, "fc-1")


def test_api_dispatches_to_d1_adapter_when_configured(monkeypatch):
    import cin_forecast_ledger_api as api
    monkeypatch.setenv("CIN_FORECAST_D1_WORKER_URL", "https://cin-ledger.example.workers.dev")
    monkeypatch.setenv("CIN_FORECAST_D1_WORKER_TOKEN", "service-secret")
    monkeypatch.delenv("CIN_FORECAST_DB_PATH", raising=False)
    from app import cin_forecast_d1_adapter as app_adapter
    monkeypatch.setattr(app_adapter, "get_forecast", lambda _path, forecast_id: {"forecast_id": forecast_id})
    assert api._ledger_call(api.get_forecast, api._database_path(), "fc-remote") == {
        "forecast_id": "fc-remote"
    }
