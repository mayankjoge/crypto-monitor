# Remaining limitations

- Forecasting, predictive modelling, and backtesting are intentionally not implemented; the dashboard does not make predictions.
- CoinGecko public API rate limits and availability are outside the app's control. A failed refresh uses cached data when available and labels it stale; otherwise an error is displayed.
- The API history endpoint covers periods up to 365 days. Intraday observations may be sampled to daily UTC closes for consistent SMA and volatility calculations.
- The watchlist is local to the browser and is not synchronized across devices.
- No alternate provider fallback (such as Binance) is implemented.
