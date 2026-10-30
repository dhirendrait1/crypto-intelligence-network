import test from "node:test";
import assert from "node:assert/strict";
import worker from "../src/index.js";

const env = { CIN_FORECAST_WORKER_TOKEN: "worker-test-secret", CIN_FORECAST_DB: {} };
const request = (path, body, token = "worker-test-secret", method = "POST") =>
  new Request("https://worker.example" + path, {
    method,
    headers: token === null ? {} : { authorization: "Bearer " + token, "content-type": "application/json" },
    body: body === null ? undefined : JSON.stringify(body),
  });

test("rejects missing and incorrect bearer credentials", async () => {
  const missing = await worker.fetch(request("/v1/ledger", { operation: "get_forecast", payload: {} }, null), env);
  const wrong = await worker.fetch(request("/v1/ledger", { operation: "get_forecast", payload: {} }, "wrong"), env);
  assert.equal(missing.status, 401);
  assert.equal(wrong.status, 401);
});

test("rejects methods and paths outside the single API endpoint", async () => {
  const method = await worker.fetch(request("/v1/ledger", null, "worker-test-secret", "GET"), env);
  const path = await worker.fetch(request("/v1/admin", {}, "worker-test-secret"), env);
  assert.equal(method.status, 404);
  assert.equal(path.status, 404);
});

test("rejects unsupported operations instead of accepting arbitrary SQL", async () => {
  const response = await worker.fetch(request("/v1/ledger", {
    operation: "execute_sql",
    payload: { sql: "DROP TABLE cin_forecasts" },
  }), env);
  assert.equal(response.status, 422);
  assert.match((await response.json()).error, /unsupported ledger operation/);
});

test("enforces request body size before JSON parsing", async () => {
  const body = JSON.stringify({ operation: "get_forecast", payload: { padding: "x".repeat(70000) } });
  const response = await worker.fetch(new Request("https://worker.example/v1/ledger", {
    method: "POST",
    headers: { authorization: "Bearer worker-test-secret", "content-type": "application/json" },
    body,
  }), env);
  assert.equal(response.status, 413);
});


test("rejects malformed forecast, observation, and evaluation payloads before database access", async () => {
  const invalidForecast = await worker.fetch(request("/v1/ledger", {
    operation: "create_forecast",
    payload: { forecast: {
      forecast_id: "fc-1", asset_id: "BTC-USD", metric: "price", value: 100,
      unit: "USD", source_id: "test", created_at: "2026-10-30T10:00:00Z",
      target_at: "2026-10-30T11:00:00Z",
    } },
  }), env);
  const invalidObservation = await worker.fetch(request("/v1/ledger", {
    operation: "insert_observation",
    payload: { observation: {
      observation_id: "obs-1", asset_id: "BTC-USD", metric: "price", value: 100,
      unit: "USD", source_id: "test", observed_at: "2026-10-30T11:00:00Z",
      retrieved_at: "2026-10-30T10:59:00Z",
    } },
  }), env);
  const invalidEvaluation = await worker.fetch(request("/v1/ledger", {
    operation: "evaluate_forecast",
    payload: { forecast_id: "fc-1", evaluated_at: "not-a-time" },
  }), env);
  assert.equal(invalidForecast.status, 422);
  assert.equal(invalidObservation.status, 422);
  assert.equal(invalidEvaluation.status, 422);
});

test("rejects invalid list limits instead of passing unsafe values to D1", async () => {
  const response = await worker.fetch(request("/v1/ledger", {
    operation: "list_forecasts",
    payload: { limit: 501 },
  }), env);
  assert.equal(response.status, 422);
  assert.match((await response.json()).error, /invalid list limit/);
});

test("returns a sanitized retryable response when the D1 binding is missing", async () => {
  const response = await worker.fetch(request(" /v1/ledger".trim(), {
    operation: "get_forecast",
    payload: { forecast_id: "fc-missing-db" },
  }), { CIN_FORECAST_WORKER_TOKEN: "worker-test-secret" });
  assert.equal(response.status, 503);
  const body = await response.json();
  assert.match(body.error, /temporarily unavailable/);
});

test("does not expose database or quota internals when storage rejects a write", async () => {
  const brokenDb = {
    prepare() {
      return {
        bind() { return this; },
        first() { throw new Error("D1_ERROR: daily write quota exceeded; internal detail"); },
      };
    },
  };
  const response = await worker.fetch(request("/v1/ledger", {
    operation: "create_forecast",
    payload: {
      forecast: {
        forecast_id: "fc-quota", asset_id: "BTC-USD", metric: "price",
        value: 70000, unit: "USD", source_id: "test",
        created_at: "2026-10-30T10:00:00Z",
        target_at: "2026-10-30T11:00:00Z",
      },
      recorded_at: "2026-10-30T10:00:01Z",
    },
  }), { CIN_FORECAST_WORKER_TOKEN: "worker-test-secret", CIN_FORECAST_DB: brokenDb });
  assert.equal(response.status, 503);
  const body = await response.json();
  assert.match(body.error, /temporarily unavailable/);
  assert.doesNotMatch(body.error, /quota|D1_ERROR|internal detail/);
});

