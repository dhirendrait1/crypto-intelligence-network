CREATE TABLE IF NOT EXISTS cin_forecasts (
  forecast_id TEXT PRIMARY KEY,
  asset_id TEXT NOT NULL,
  metric TEXT NOT NULL,
  unit TEXT NOT NULL,
  created_at TEXT NOT NULL,
  payload_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cin_forecasts_asset_created
  ON cin_forecasts(asset_id, created_at DESC, forecast_id);
CREATE TABLE IF NOT EXISTS cin_forecast_observations (
  observation_id TEXT PRIMARY KEY,
  asset_id TEXT NOT NULL,
  metric TEXT NOT NULL,
  unit TEXT NOT NULL,
  observed_at TEXT NOT NULL,
  payload_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cin_forecast_observations_match
  ON cin_forecast_observations(asset_id, metric, unit, observed_at);
CREATE TABLE IF NOT EXISTS cin_forecast_evaluations (
  forecast_id TEXT PRIMARY KEY,
  observation_id TEXT NOT NULL,
  evaluated_at TEXT NOT NULL,
  result_json TEXT NOT NULL
);
