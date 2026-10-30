/**
 * CIN forecast ledger D1 gateway.
 * Exposes a fixed operation allowlist; never accepts SQL or table names.
 */
const json = (data, status = 200) => new Response(JSON.stringify(data), {
  status, headers: { "content-type": "application/json; charset=utf-8",
    "cache-control": "no-store" }
});
const bad = (message, status = 400) => json({ error: message }, status);
const finite = value => typeof value === "number" && Number.isFinite(value);
const text = (value, max = 160) => typeof value === "string" && value.trim() &&
  value.length <= max && !/[\u0000-\u001f\u007f]/.test(value);
const iso = value => typeof value === "string" && !Number.isNaN(Date.parse(value)) &&
  /(?:Z|[+-]\d{2}:\d{2})$/.test(value);
const stable = value => {
  if (Array.isArray(value)) return "[" + value.map(stable).join(",") + "]";
  if (value && typeof value === "object")
    return "{" + Object.keys(value).sort().map(key => JSON.stringify(key) + ":" + stable(value[key])).join(",") + "}";
  return JSON.stringify(value);
};

async function forecast(env, id) {
  const row = await env.CIN_FORECAST_DB.prepare(
    "SELECT payload_json FROM cin_forecasts WHERE forecast_id = ?"
  ).bind(id).first();
  return row ? JSON.parse(row.payload_json) : null;
}
async function observation(env, id) {
  const row = await env.CIN_FORECAST_DB.prepare(
    "SELECT payload_json FROM cin_forecast_observations WHERE observation_id = ?"
  ).bind(id).first();
  return row ? JSON.parse(row.payload_json) : null;
}
function validateForecast(f, recordedAt) {
  if (!f || !text(f.forecast_id) || !text(f.asset_id) || !text(f.metric) ||
      !finite(f.value) || !text(f.unit, 40) || !text(f.source_id) ||
      !iso(f.created_at) || !iso(f.target_at) || !iso(recordedAt) ||
      Date.parse(f.target_at) <= Date.parse(f.created_at))
    throw new Error("invalid forecast payload");
  return { ...f, recorded_at: recordedAt };
}
function validateObservation(o) {
  if (!o || !text(o.observation_id) || !text(o.asset_id) || !text(o.metric) ||
      !finite(o.value) || !text(o.unit, 40) || !text(o.source_id) ||
      !iso(o.observed_at) || !iso(o.retrieved_at) ||
      Date.parse(o.retrieved_at) < Date.parse(o.observed_at))
    throw new Error("invalid observation payload");
  return o;
}
async function insertImmutable(env, table, idColumn, id, item) {
  const payload = JSON.stringify(item);
  const existing = await env.CIN_FORECAST_DB.prepare(
    `SELECT payload_json FROM ${table} WHERE ${idColumn} = ?`
  ).bind(id).first();
  if (existing) {
    const old = JSON.parse(existing.payload_json);
    if (table === "cin_forecasts") {
      const originalRecordedAt = old.recorded_at;
      delete old.recorded_at;
      const copy = { ...item };
      delete copy.recorded_at;
      if (stable(old) !== stable(copy)) throw new Error("ID already exists with different content");
      return { ...old, recorded_at: originalRecordedAt };
    }
    if (stable(old) !== stable(item)) throw new Error("ID already exists with different content");
    return old;
  }
  if (table === "cin_forecasts") {
    await env.CIN_FORECAST_DB.prepare(
      "INSERT OR IGNORE INTO cin_forecasts (forecast_id, asset_id, metric, unit, created_at, payload_json) VALUES (?, ?, ?, ?, ?, ?)"
    ).bind(id, item.asset_id, item.metric, item.unit, item.created_at, payload).run();
  } else {
    await env.CIN_FORECAST_DB.prepare(
      "INSERT OR IGNORE INTO cin_forecast_observations (observation_id, asset_id, metric, unit, observed_at, payload_json) VALUES (?, ?, ?, ?, ?, ?)"
    ).bind(id, item.asset_id, item.metric, item.unit, item.observed_at, payload).run();
  }
  const saved = await env.CIN_FORECAST_DB.prepare(
    `SELECT payload_json FROM ${table} WHERE ${idColumn} = ?`
  ).bind(id).first();
  const value = saved && JSON.parse(saved.payload_json);
  if (!value || (table !== "cin_forecasts" && stable(value) !== stable(item)))
    throw new Error("ID already exists with different content");
  if (table === "cin_forecasts") {
    const a = { ...value }, b = { ...item }; delete a.recorded_at; delete b.recorded_at;
    if (stable(a) !== stable(b)) throw new Error("ID already exists with different content");
  }
  return value;
}
async function handle(env, op, p) {
  const db = env.CIN_FORECAST_DB;
  if (!db) throw new Error("D1 binding CIN_FORECAST_DB is unavailable");
  switch (op) {
    case "create_forecast": {
      const item = validateForecast(p.forecast, p.recorded_at);
      return insertImmutable(env, "cin_forecasts", "forecast_id", item.forecast_id, item);
    }
    case "insert_observation": {
      const item = validateObservation(p.observation);
      return insertImmutable(env, "cin_forecast_observations", "observation_id", item.observation_id, item);
    }
    case "get_forecast": {
      if (!text(p.forecast_id)) throw new Error("invalid forecast_id");
      return forecast(env, p.forecast_id);
    }
    case "get_evaluation": {
      if (!text(p.forecast_id)) throw new Error("invalid forecast_id");
      const row = await db.prepare("SELECT result_json FROM cin_forecast_evaluations WHERE forecast_id = ?")
        .bind(p.forecast_id).first();
      return row ? JSON.parse(row.result_json) : null;
    }
    case "list_forecasts": {
      const requested = p.limit === undefined ? 100 : Number(p.limit);
      if (!Number.isInteger(requested) || requested < 1 || requested > 500)
        throw new Error("invalid list limit");
      const limit = requested;
      const rows = p.asset_id
        ? await db.prepare("SELECT payload_json FROM cin_forecasts WHERE asset_id = ? ORDER BY created_at DESC, forecast_id LIMIT ?").bind(p.asset_id, limit).all()
        : await db.prepare("SELECT payload_json FROM cin_forecasts ORDER BY created_at DESC, forecast_id LIMIT ?").bind(limit).all();
      return (rows.results || []).map(r => JSON.parse(r.payload_json));
    }
    case "list_evaluations": {
      const requested = p.limit === undefined ? 100 : Number(p.limit);
      if (!Number.isInteger(requested) || requested < 1 || requested > 500)
        throw new Error("invalid list limit");
      const limit = requested;
      const rows = p.asset_id
        ? await db.prepare("SELECT e.result_json FROM cin_forecast_evaluations e JOIN cin_forecasts f ON f.forecast_id=e.forecast_id WHERE f.asset_id=? ORDER BY e.evaluated_at DESC,e.forecast_id LIMIT ?").bind(p.asset_id, limit).all()
        : await db.prepare("SELECT result_json FROM cin_forecast_evaluations ORDER BY evaluated_at DESC,forecast_id LIMIT ?").bind(limit).all();
      return (rows.results || []).map(r => JSON.parse(r.result_json));
    }
    case "evaluate_forecast": {
      if (!text(p.forecast_id) || !iso(p.evaluated_at))
        throw new Error("invalid evaluation payload");
      const f = await forecast(env, p.forecast_id);
      if (!f) throw new Error("forecast_id not found");
      const target = Date.parse(f.target_at), now = Date.parse(p.evaluated_at);
      const lag = Number(p.max_observation_lag_seconds ?? 3600);
      if (!Number.isFinite(now) || now < target) throw new Error("forecast horizon has not closed");
      if (!Number.isInteger(lag) || lag < 0 || lag > 604800) throw new Error("invalid observation lag");
      const prior = await db.prepare("SELECT result_json FROM cin_forecast_evaluations WHERE forecast_id=?")
        .bind(p.forecast_id).first();
      if (prior) return JSON.parse(prior.result_json);
      const candidate = await db.prepare(
        "SELECT payload_json FROM cin_forecast_observations WHERE asset_id=? AND metric=? AND unit=? AND observed_at>=? AND observed_at<=? ORDER BY ABS(julianday(observed_at)-julianday(?)), observed_at, observation_id LIMIT 1"
      ).bind(f.asset_id, f.metric, f.unit, f.target_at, new Date(target + lag * 1000).toISOString(), f.target_at).first();
      const o = candidate ? JSON.parse(candidate.payload_json) : null;
      if (!o) return { forecast_id:p.forecast_id, status:"not_evaluable",
        reason:"no_matching_observation_within_horizon_tolerance", target_at:f.target_at,
        max_observation_lag_seconds:lag };
      const error = o.value - f.value;
      const result = { forecast_id:f.forecast_id, status:"evaluated", reason:"horizon_observation_comparable", metric:f.metric,
        unit:f.unit, predicted_value:f.value, actual_value:o.value, error,
        absolute_error:Math.abs(error),
        absolute_percentage_error:o.value === 0 ? null : Math.abs(error/Math.abs(o.value))*100,
        percentage_error_reason:o.value === 0 ? "actual_value_is_zero" : undefined,
        target_at:f.target_at,
        observation_id:o.observation_id, source_id:o.source_id, observed_at:o.observed_at,
        evaluated_at:p.evaluated_at, asset_id:f.asset_id,
        observation_retrieved_at:o.retrieved_at, max_observation_lag_seconds:lag };
      await db.prepare("INSERT OR IGNORE INTO cin_forecast_evaluations (forecast_id, observation_id, evaluated_at, result_json) VALUES (?, ?, ?, ?)")
        .bind(f.forecast_id, o.observation_id, p.evaluated_at, JSON.stringify(result)).run();
      const saved = await db.prepare("SELECT result_json FROM cin_forecast_evaluations WHERE forecast_id=?")
        .bind(f.forecast_id).first();
      return saved ? JSON.parse(saved.result_json) : result;
    }
    default: throw new Error("unsupported ledger operation");
  }
}
export default {
  async fetch(request, env) {
    if (request.method !== "POST" || new URL(request.url).pathname !== "/v1/ledger")
      return bad("not found", 404);
    const expected = env.CIN_FORECAST_WORKER_TOKEN;
    const auth = request.headers.get("authorization") || "";
    if (!expected || !auth.startsWith("Bearer ")) return bad("unauthorized", 401);
    const supplied = new TextEncoder().encode(auth.slice(7));
    const wanted = new TextEncoder().encode(expected);
    if (supplied.length !== wanted.length) return bad("unauthorized", 401);
    let mismatch = 0;
    for (let i = 0; i < supplied.length; i++) mismatch |= supplied[i] ^ wanted[i];
    if (mismatch !== 0) return bad("unauthorized", 401);
    let raw;
    try { raw = await request.text(); } catch { return bad("invalid request"); }
    if (new TextEncoder().encode(raw).length > 65536) return bad("request too large", 413);
    let body;
    try { body = JSON.parse(raw); } catch { return bad("invalid JSON"); }
    if (!body || !text(body.operation, 60) || !body.payload || typeof body.payload !== "object")
      return bad("invalid request");
    try { return json({ result: await handle(env, body.operation, body.payload) }); }
    catch (error) {
      const message = String(error?.message || "ledger operation failed");
      const status = /not found/.test(message) ? 404 : /already exists|invalid|horizon|unsupported/.test(message) ? 422 : 500;
      return bad(message, status);
    }
  }
};
