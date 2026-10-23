# CIN coin screening — Step 2

The `/coin-screening` endpoint is a read-only research-prioritization screen. It does not execute trades or provide a safety certification.

## Endpoint

`GET /coin-screening`

Query parameters:
- `vs_currency`: quote currency, default `usd`.
- `per_page`: number of top market-cap rows to request, 1–100; default 50.
- `min_score`: minimum raw heuristic score, 0–100.
- `asset_type`: `all`, `growth`, `stablecoin`, `wrapped_or_staked`, `commodity_backed`, or `other_crypto`.

Examples:
- `/coin-screening?per_page=20`
- `/coin-screening?asset_type=growth&per_page=50`
- `/coin-screening?asset_type=commodity_backed`

## Score and interpretation

The raw score is a transparent metric checklist with weights: market cap 20, 24-hour volume 20, volume/market-cap ratio 20, FDV gap 15, circulating/total supply ratio 15, and a 24-hour price-change band 10. Missing metrics receive no points and produce warnings.

The raw score is not a forecast, endorsement, buy/sell signal, or safety rating. A stablecoin can score highly on liquidity metrics without being a growth asset. Therefore each row also returns:
- `screen_profile`: `growth_research`, `stablecoin_monitoring`, `wrapped_staked_monitoring`, or `commodity_backed_monitoring`.
- `growth_candidate_eligible`: true only for assets classified by the current heuristic as `other_crypto`.
- `screen_band`: non-growth categories are labeled `excluded_non_growth_asset` so they are not mistaken for growth candidates.

The `growth` filter excludes assets classified as stablecoins, wrapped/staked tokens, or commodity-backed tokens. Remaining `other_crypto` assets are **not verified growth investments**; this is a broad research bucket, not a prediction of growth.

## Classification caveats

Classification uses symbol/name/ID heuristics, not an authoritative asset registry. Current commodity-backed examples include XAUT and PAXG, plus token names containing phrases such as “tokenized gold” or “commodity-backed”. False positives and false negatives are possible. Independently verify reserves, redemption rights, issuer/custody risk, token contracts, and asset structure.

The screen does not yet validate token unlock schedules, project utility, developer activity, audits, exploits, holder concentration, exchange-specific order-book depth, or market integrity. Top market-cap data does not cover every token. Provider data may be cached or stale; always inspect `data_mode`, `stale_data_warning`, and `provider_error_code`.

## Operating boundary

CIN is for public-data research, analysis, monitoring, and alerts only. No trade/order execution, wallet control, private-key handling, or fund movement is implemented or intended.
