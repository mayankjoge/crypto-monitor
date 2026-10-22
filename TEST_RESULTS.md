# Test results
Environment: sandbox with NO access to CoinGecko/Binance and no browser. 16 offline unit/API tests passed, plus a curl smoke test of the server in mock mode. Live data and the visual UI were **not** tested.

| # | Criterion | Result | Notes |
|---|-----------|--------|-------|
| 1 | App starts per docs | Passed (mock mode only) | Started with `MOCK_MODE=1`; routes returned 200. Live start not tested |
| 2 | Data loads/validated or clear error | Partial | Validation and 503/error paths unit tested; real CoinGecko never contacted |
| 3 | Listing fields, search, sort, filter | Not tested | Fields verified via API; search/sort/filter are client JS, syntax-checked only |
| 4 | Charts + period change | Partial | API returns correct point counts for 7/30/90/365 (365 capped at 365 points). Rendering not tested |
| 5 | Watchlist | Not tested | localStorage-based, never run in a browser |
| 6 | Rankings/screening follow rules | Passed | Unit and API tests (volume ordering, thresholds, missing metrics excluded) |
| 7 | Indicators correct | Passed | SMA and volatility match hand-computed values |
| 8 | Forecasts disclose details | Partial | Horizon, method, errors vs baselines and range shown in agent output; tested via API only, not in a browser |
| 9 | Backtests no leakage | Passed | Unit test: altering future prices does not change earlier predictions (forecast backtest only; no trading backtest) |
| 10 | Failures/stale/missing/invalid inputs | Passed (simulated) | Simulated outage, 429, stale cache, malformed/duplicate rows, bad params (400). Real failures not observed |
| 11 | Desktop/mobile usable | Not tested | Responsive CSS written, never viewed |
| 12 | No credentials client-side/logs | Passed (static check) | Test greps static files for key references |
| 13 | Setup matches app | Partial | Run commands exercised except fresh-venv install and live mode |
