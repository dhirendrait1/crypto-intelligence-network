import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { DatabaseSync } from "node:sqlite";
import worker from "../src/index.js";

function makeD1() {
  const db = new DatabaseSync(":memory:");
  db.exec(readFileSync("worker/migrations/0001_forecast_ledger.sql", "utf8"));
  return {
    prepare(sql) {
      let values = [];
      const statement = {
        bind(...args) { values = args; return statement; },
        first() { return db.prepare(sql).get(...values) ?? null; },
        all() { return { results: db.prepare(sql).all(...values) }; },
        run() {
          const result = db.prepare(sql).run(...values);
          return { success: true, meta: { changes: Number(result.changes) } };
        },
      };
      return statement;
    },
    close() { db.close(); },
  };
}

const token = "worker-test-secret";
async function call(env, operation, payload) {
  const response = await worker.fetch(new Request("https://worker.example/v1/ledger", {
    method: "POST",
    headers: { authorization: `Bearer ${token}`, "content-type": "application/json" },
    body: JSON.stringify({ operation, payload }),
  }), env);
  return { status: response.status, body: await response.json() };
}

test("persists immutable forecasts and observations and evaluates the nearest horizon observation once", async () => {
  const db = makeD1();
  const env = { CIN_FORECAST_WORKER_TOKEN: token, CIN_FORECAST_DB: db };
  const forecast = {
    forecast_id: "fc-btc-1", asset_id: "BTC-USD", metric: "price",
    value: 70000, unit: "USD", source_id: "cin-model-v1",
    created_at: "2026-10-30T10:00:00+00:00",
    target_at: "2026-10-30T11:00:00+00:00",
    invalidation_conditions: { below: 68000 },
  };

  const created = await call(env, "create_forecast", {
    forecast, recorded_at: "2026-10-30T10:00:05+00:00",
  });
  assert.equal(created.status, 200);
  assert.equal(created.body.result.forecast_id, forecast.forecast_id);\n  assert.equal(created.body.result.created_at, "2026-10-30T10:00:00.000Z");\n  assert.equal(created.body.result.target_at, "2026-10-30T11:00:00.000Z");

  const replay = await call(env, "create_forecast", {
    forecast, recorded_at: "2026-10-30T10:05:00+00:00",
  });
  assert.equal(replay.status, 200);
  assert.equal(replay.body.result.recorded_at, "2026-10-30T10:00:05.000Z");

  const conflict = await call(env, "create_forecast", {
    forecast: { ...forecast, value: 71000 },
    recorded_at: "2026-10-30T10:05:00+00:00",
  });
  assert.equal(conflict.status, 422);

  const observation = (id, observedAt, value) => ({
    observation_id: id, asset_id: "BTC-USD", metric: "price", value,
    unit: "USD", source_id: "coinbase-public", observed_at: observedAt,
    retrieved_at: "2026-10-30T11:05:00+00:00",
  });
  const first = await call(env, "insert_observation", {
    observation: observation("obs-near", "2026-10-30T11:02:00+00:00", 69500),
  });
  const second = await call(env, "insert_observation", {
    observation: observation("obs-far", "2026-10-30T11:04:00+00:00", 69000),
  });
  assert.equal(first.status, 200);
  assert.equal(second.status, 200);

  const evaluated = await call(env, "evaluate_forecast", {
    forecast_id: forecast.forecast_id,
    evaluated_at: "2026-10-30T11:06:00+00:00",
    max_observation_lag_seconds: 600,
  });
  assert.equal(evaluated.status, 200);
  assert.equal(evaluated.body.result.status, "evaluated");
  assert.equal(evaluated.body.result.observation_id, "obs-near");
  assert.equal(evaluated.body.result.error, -500);

  const repeated = await call(env, "evaluate_forecast", {
    forecast_id: forecast.forecast_id,
    evaluated_at: "2026-10-30T12:00:00+00:00",
    max_observation_lag_seconds: 600,
  });
  assert.equal(repeated.body.result.evaluated_at, "2026-10-30T11:06:00+00:00");

  const detail = await call(env, "get_forecast", { forecast_id: forecast.forecast_id });
  const evaluation = await call(env, "get_evaluation", { forecast_id: forecast.forecast_id });
  const forecasts = await call(env, "list_forecasts", { asset_id: "BTC-USD", limit: 10 });
  const evaluations = await call(env, "list_evaluations", { asset_id: "BTC-USD", limit: 10 });
  assert.equal(detail.body.result.forecast_id, forecast.forecast_id);
  assert.equal(evaluation.body.result.observation_id, "obs-near");
  assert.equal(forecasts.body.result.length, 1);
  assert.equal(evaluations.body.result.length, 1);
  db.close();
});


test("canonical payload comparison accepts reordered nested JSON keys", async () => {
  const db = makeD1();
  const env = { CIN_FORECAST_WORKER_TOKEN: token, CIN_FORECAST_DB: db };
  const base = {
    forecast_id: "fc-canonical", asset_id: "ETH-USD", metric: "price",
    value: 3000, unit: "USD", source_id: "test",
    created_at: "2026-10-30T10:00:00Z", target_at: "2026-10-30T11:00:00Z",
    metadata: { model: "v1", inputs: { volatility: 0.2, horizon: "1h" } },
  };
  const first = await call(env, "create_forecast", {
    forecast: base, recorded_at: "2026-10-30T10:00:01Z",
  });
  const replay = await call(env, "create_forecast", {
    forecast: {
      ...base,
      metadata: { inputs: { horizon: "1h", volatility: 0.2 }, model: "v1" },
    },
    recorded_at: "2026-10-30T10:01:00Z",
  });
  assert.equal(first.status, 200);
  assert.equal(replay.status, 200);
  assert.equal(replay.body.result.recorded_at, "2026-10-30T10:00:01Z");
  db.close();
});

test("concurrent duplicate forecast inserts preserve one immutable record", async () => {
  const db = makeD1();
  const env = { CIN_FORECAST_WORKER_TOKEN: token, CIN_FORECAST_DB: db };
  const forecast = {
    forecast_id: "fc-race", asset_id: "BTC-USD", metric: "price",
    value: 70000, unit: "USD", source_id: "test",
    created_at: "2026-10-30T10:00:00Z", target_at: "2026-10-30T11:00:00Z",
  };
  const [one, two] = await Promise.all([
    call(env, "create_forecast", { forecast, recorded_at: "2026-10-30T10:00:01Z" }),
    call(env, "create_forecast", { forecast, recorded_at: "2026-10-30T10:00:02Z" }),
  ]);
  assert.equal(one.status, 200);
  assert.equal(two.status, 200);
  assert.equal(one.body.result.recorded_at, two.body.result.recorded_at);
  const saved = await call(env, "get_forecast", { forecast_id: "fc-race" });
  assert.equal(saved.body.result.forecast_id, "fc-race");
  db.close();
});

test("concurrent evaluations return the single persisted first result", async () => {
  const db = makeD1();
  const env = { CIN_FORECAST_WORKER_TOKEN: token, CIN_FORECAST_DB: db };
  const forecast = {
    forecast_id: "fc-eval-race", asset_id: "BTC-USD", metric: "price",
    value: 70000, unit: "USD", source_id: "test",
    created_at: "2026-10-30T10:00:00Z", target_at: "2026-10-30T11:00:00Z",
  };
  await call(env, "create_forecast", { forecast, recorded_at: "2026-10-30T10:00:01Z" });
  await call(env, "insert_observation", { observation: {
    observation_id: "obs-eval-race", asset_id: "BTC-USD", metric: "price",
    value: 69900, unit: "USD", source_id: "test",
    observed_at: "2026-10-30T11:01:00Z", retrieved_at: "2026-10-30T11:02:00Z",
  } });
  const [one, two] = await Promise.all([
    call(env, "evaluate_forecast", { forecast_id: "fc-eval-race", evaluated_at: "2026-10-30T11:03:00Z" }),
    call(env, "evaluate_forecast", { forecast_id: "fc-eval-race", evaluated_at: "2026-10-30T11:04:00Z" }),
  ]);
  assert.equal(one.status, 200);
  assert.equal(two.status, 200);
  assert.deepEqual(one.body.result, two.body.result);
  db.close();
});

test("concurrent forecast retries preserve the first write and reject conflicting content", async () => {
  const db = makeD1();
  const env = { CIN_FORECAST_WORKER_TOKEN: token, CIN_FORECAST_DB: db };
  const forecast = {
    forecast_id: "fc-race-1", asset_id: "ETH-USD", metric: "price",
    value: 2500, unit: "USD", source_id: "cin-model-v1",
    created_at: "2026-10-30T10:00:00Z",
    target_at: "2026-10-30T12:00:00Z",
  };
  const [a, b] = await Promise.all([
    call(env, "create_forecast", { forecast, recorded_at: "2026-10-30T10:00:01Z" }),
    call(env, "create_forecast", { forecast, recorded_at: "2026-10-30T10:00:02Z" }),
  ]);
  assert.equal(a.status, 200);
  assert.equal(b.status, 200);
  assert.equal(a.body.result.recorded_at, b.body.result.recorded_at);
  assert.equal(a.body.result.recorded_at, "2026-10-30T10:00:01Z");

  const [same, conflict] = await Promise.all([
    call(env, "create_forecast", { forecast, recorded_at: "2026-10-30T10:01:00Z" }),
    call(env, "create_forecast", {
      forecast: { ...forecast, value: 2600 },
      recorded_at: "2026-10-30T10:01:00Z",
    }),
  ]);
  assert.equal(same.status, 200);
  assert.equal(conflict.status, 422);
  db.close();
});

test("concurrent observation retries are idempotent and conflicting IDs fail closed", async () => {
  const db = makeD1();
  const env = { CIN_FORECAST_WORKER_TOKEN: token, CIN_FORECAST_DB: db };
  const observation = {
    observation_id: "obs-race-1", asset_id: "ETH-USD", metric: "price",
    value: 2501, unit: "USD", source_id: "coinbase-public",
    observed_at: "2026-10-30T12:00:01Z",
    retrieved_at: "2026-10-30T12:00:02Z",
  };
  const [a, b] = await Promise.all([
    call(env, "insert_observation", { observation }),
    call(env, "insert_observation", { observation }),
  ]);
  assert.equal(a.status, 200);
  assert.equal(b.status, 200);
  assert.deepEqual(a.body.result, b.body.result);

  const conflict = await call(env, "insert_observation", {
    observation: { ...observation, value: 2499 },
  });
  assert.equal(conflict.status, 422);
  db.close();
});

test("canonicalizes offset timestamps before storing and comparing ledger rows", async () => {
  const db = makeD1();
  const env = { CIN_FORECAST_WORKER_TOKEN: token, CIN_FORECAST_DB: db };
  const created = await call(env, "create_forecast", {
    forecast: {
      forecast_id: "fc-offset-1", asset_id: "BTC-USD", metric: "price",
      value: 70000, unit: "USD", source_id: "cin-model-v1",
      created_at: "2026-10-30T12:00:00+02:00",
      target_at: "2026-10-30T13:00:00+02:00",
    },
    recorded_at: "2026-10-30T12:00:05+02:00",
  });
  assert.equal(created.status, 200);
  assert.equal(created.body.result.created_at, "2026-10-30T10:00:00.000Z");
  assert.equal(created.body.result.target_at, "2026-10-30T11:00:00.000Z");
  assert.equal(created.body.result.recorded_at, "2026-10-30T10:00:05.000Z");

  const inserted = await call(env, "insert_observation", {
    observation: {
      observation_id: "obs-offset-1", asset_id: "BTC-USD", metric: "price",
      value: 69900, unit: "USD", source_id: "coinbase-public",
      observed_at: "2026-10-30T13:02:00+02:00",
      retrieved_at: "2026-10-30T13:03:00+02:00",
    },
  });
  assert.equal(inserted.status, 200);
  assert.equal(inserted.body.result.observed_at, "2026-10-30T11:02:00.000Z");
  assert.equal(inserted.body.result.retrieved_at, "2026-10-30T11:03:00.000Z");
  db.close();
});
\n