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
