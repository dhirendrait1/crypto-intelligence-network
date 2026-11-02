# CIN Market Data Provider Policy

## /market-data

- Primary provider: Coinbase Exchange public REST API, without API credentials.
- Supported asset IDs in this initial adapter: `bitcoin` → `BTC-USD`; `ethereum` → `ETH-USD`.
- Quote currency: USD only. Other quote currencies are rejected; CIN does not silently substitute a USD/USDT or other market.
- Provider requests are read-only, use a 12-second timeout, and enforce a bounded response size.
- Price and 24-hour base volume come from the Coinbase product statistics endpoint. The normalized `total_volume_24h` value is denominated in the base asset (for example, BTC or ETH), and the response includes `total_volume_24h_unit` / `volume_24h_currency`; it must not be interpreted as USD quote turnover. The percentage change is derived from the reported 24-hour open and last prices.
- The ticker timestamp drives the existing 15-minute freshness policy. Stale or unknown timestamps are not analysis-eligible.
- Coinbase Exchange product statistics do not provide market capitalization. CIN returns `market_cap: null` and an explicit limitation warning; it does not fabricate or infer market cap.
- Unsupported asset IDs are reported as missing. The adapter does not call CoinGecko or another substitute provider.

This is an initial, deliberately narrow adapter. Expand the asset allowlist only with tests proving the exact Coinbase USD product mapping. This change is not a live-provider certification and does not change the deployed service.
