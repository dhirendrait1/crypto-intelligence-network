# CIN shortlist offline JSON interface (development only)

The CLI evaluates **provided** numeric factors through the deterministic, read-only scoring core. It does **not** collect live data, substantiate supplied scores, calculate trade opportunities, or make any recommendation to buy or sell. Production integration requires provenance, per-factor freshness, risk policies and independently validated market inputs.

## Offline execution

```bash
python -m unittest tests.test_cin_shortlist_scoring tests.test_cin_shortlist_offline_cli -v
python cin_shortlist_offline_cli.py snapshot.json
```

Input JSON contract: a top-level object with exactly one `candidates` array (maximum 100), each candidate containing exactly `symbol`, `scores` and `gates`. Every score dimension in `cin_shortlist_scoring.WEIGHTS` must be provided for a numeric total; four boolean eligibility gates must be explicitly known. Any missing score/gate yields `insufficient_data`; a failed gate yields `rejected` regardless of score. Bad types, unknown fields or duplicate symbols cause a controlled input error. Output retains every candidate and ranks eligible candidates by score, breaking ties by symbol. Input files are limited to 2 MB.

Use source-verified normalized scores only. Never interpret the sample numbers as market forecasts. The weights and grades are design defaults, not backtested predictive performance. No exchanges, wallets, orders, fund movement, secrets, Render/Cloudflare activation or paid infrastructure are involved.
