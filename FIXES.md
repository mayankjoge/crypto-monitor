# Repair notes

The main bugs and reliability gaps addressed in this revision:

- **Historical chart granularity:** stopped forcing `interval=daily` on the public CoinGecko request. The provider now requests a warm-up window and selects the last observation of each UTC day before calculating daily SMA and volatility.
- **Malformed API payloads:** history validation now checks data shapes, timestamps, prices, and volume values row by row; malformed rows are skipped instead of leaking `ValueError`/`TypeError` into a 500 response. Timestamps are normalized before duplicate removal.
- **Data and cache resilience:** negative optional market metrics are treated as unavailable, turnover requires a positive market cap, cache access is protected by a lock, invalid cache-age environment variables get safe defaults, and provider/auth/rate-limit errors are surfaced clearly.
- **Async chart race:** a slow history response for an old row or period can no longer overwrite the chart for the user's latest selection.
- **External chart dependency:** replaced the Chart.js CDN dependency with a small Canvas chart renderer for price, volume, SMA 7, and SMA 30, including hover/tap details. This means the chart itself does not need an external JavaScript library to load.
- **Dashboard usability:** added visible sort direction and `aria-sort`, keyboard row selection, clearer empty-watchlist messaging, numeric screen-field bounds, more useful loading/error states, responsive chart sizing, and gainers/losers filters that match the rounded percentage shown in the table.
- **Run experience:** added `run.sh` and `run.bat` with mock mode enabled by default, plus clearer setup/configuration docs and more regression tests.

The project still intentionally does not implement price forecasts, backtesting, or an alternate live data provider. Mock prices are synthetic, and live CoinGecko requests depend on API availability and rate limits.
