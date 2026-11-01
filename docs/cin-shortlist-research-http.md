# Opt-in read-only CIN shortlist research HTTP contract

The optional FastAPI router in `cin_shortlist_research_api.py` exposes `POST /research/shortlist/evaluate` **only when explicitly included in a separate test or application**. It is not registered by CIN's production Render patch or default app. This is intentional until provider integration, source verification, authentication/abuse controls and end-to-end validation are complete.

Request: `{"candidates":[{"symbol":"BTC","factors":{...},"gates":{...}}]}` with at most 100 candidates. The factor names and weights are defined by `cin_shortlist_scoring.WEIGHTS`. Every factor value is `{"score": 80.0, "source": "example-fixture", "observed_at": "2026-11-02T00:00:00+00:00"}`. This sample is **not** a live Bitcoin assessment. Actual timestamps must be current to pass the default 24-hour freshness check. Required gates are `security_clear`, `liquidity_sufficient`, `data_reliable`, `risk_acceptable`: all are strict booleans.

Results are ranked only when complete and eligible; missing/stale factor data becomes `insufficient_data`, and negative gates become `rejected`. Callers must not infer source verification from a supplied label. `execution_enabled` always remains `false`. No buy/sell recommendation, order, wallet, account, remote provider call, paid service or deployment occurs.

Offline test contract: `python -m unittest tests.test_cin_shortlist_research_api -v`. This milestone is a deliberately unmounted research API adapter, not an announcement that the CIN dashboard or live API is integrated.
