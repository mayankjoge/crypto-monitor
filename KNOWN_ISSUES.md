# Known issues / unfinished
- Forecasting is a simple trend model; trading-strategy backtest (fees, drawdown) not built. Agent is rule-based, not LLM-driven. Forecast quality on real data is unknown.
- Live CoinGecko integration, browser UI, watchlist, charts, mobile layout: untested.
- No Binance fallback. History limited to 365 days; free-tier rate limits can cause stale data.
- Screening uses snapshot metrics only (no volume-spike history). Mock data is synthetic.
- Flask does not auto-load `.env`.
