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
- `/coin-screening?asset_type=commodity_backed&per_page=10`

### Commodity-backed discovery

The `commodity_backed` filter uses the public CoinPaprika ticker endpoint and classifies the returned ticker universe **before** applying `per_page`. This avoids the previous behavior where commodity assets could be missed because they were outside the top market-cap page. The response includes `universe_scan` metadata:
- `scanned_universe_count`: ticker rows inspected from the provider response.
- `classified_match_count`: rows classified by CIN's heuristic as commodity-backed.
- `returned_count`: matching rows returned after `per_page`.
- `status`: `matches_found` or `no_matches_in_scanned_universe`.

This is still only the provider's returned ticker universe, not every token in existence. Classification is heuristic and can miss assets. A zero-match response means no matches were identified in the scanned provider response; it does not prove no commodity-backed tokens exist. This category-specific path uses CoinPaprika data and has a 20-second provider timeout. The response body is read with the same 5 MB maximum as the standard screening request; oversized payloads are rejected before JSON parsing.

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


## Cache state versus provider timestamp freshness

Each result exposes `provider_timestamp_status` and `provider_timestamp_age_seconds` for the provider's `last_updated` timestamp. The effective `freshness_status` may instead be `stale_cache` when provider retrieval fails and CIN falls back to cached rows. In that case `analysis_eligible` and `screening_eligible` are forced to `false`, and the growth candidate band is held, even if the provider timestamp itself appears recent. These fields describe different evidence dimensions: provider-reported update age does not make a stale-cache fallback eligible for screening. Inspect both result-level metadata and response-level `data_mode`, `cache_age_seconds`, and provider error details.


## Numeric evidence and ratio safety

Financial magnitude inputs (market cap, volume, FDV, circulating supply, and total supply) must be finite and non-negative; invalid or negative values are treated as missing evidence and do not contribute to ratios or scoring. Volume/market-cap, FDV-gap, and circulating-supply ratios are checked for finite results before exposure. If arithmetic produces a non-finite ratio, CIN returns that metric as `null`, emits a warning, and does not award points for that metric. Raw scores remain heuristic metric totals and must be interpreted alongside `analysis_eligible`, `screening_eligible`, freshness, and warning fields. This is defensive input validation, not independent verification of provider data.


## Provider identity and deterministic row handling

Before scoring, CIN requires each market row to have a non-empty string provider ID. Rows without an ID are discarded, and duplicate IDs are collapsed case-insensitively by keeping the first row in provider input order. The response `data_quality` object reports input rows, identity-less rows, duplicate IDs, and unique accepted identities. This prevents duplicate provider records from inflating result counts and makes identity cleanup visible. The policy is deterministic for a given provider response, but it does not prove that provider IDs are globally canonical or that two distinct IDs cannot refer to the same underlying asset.


## Screening market-data provider policy

The broad `/coin-screening` market universe uses the public CoinPaprika ticker endpoint as its sole market-universe provider. Provider failure returns a structured error or uses an eligible cached response under the existing cache policy; it does not silently switch to another source.

Coinbase remains the preferred public source for exact USD-quoted exchange candles in the market-candles module. Coinbase Exchange product and candle data is not a complete global market-cap-ranked token universe, so it is not substituted for CoinPaprika in broad-universe screening. Provider identity and quote currency are retained on each screening row. CoinPaprika market data is not independently verified issuer or project evidence.
