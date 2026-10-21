# Demo guide (about 5 minutes)

1. Run `./run.sh` (Windows: `run.bat`). The default is `MOCK_MODE=1`; point out the banner that states these prices are synthetic. The first run installs Flask and Requests.
2. Dashboard: check the source/fetched timestamp, search by name or symbol, sort with headers, test gainers and losers, and add/remove coins using ☆.
3. Click a coin row (or focus it and press Enter) to display daily price history. Change 7d/30d/90d/1y periods, toggle SMA 7/30, and hover the chart to inspect price, volume, and averages.
4. Signals: inspect the most-active list, change screen thresholds, and run the screen. Explain that a match is not a prediction or recommendation.
5. Open Methodology and Limitations. Mention public API limits, stale-cache behavior, local-only watchlist storage, and that forecasting/backtesting are not implemented.
6. To try live data, stop the app and start it with `MOCK_MODE=0` (PowerShell: `$env:MOCK_MODE="0"; python app.py`). If CoinGecko is unavailable, expect a clear error or stale-data warning rather than fabricated live prices.
