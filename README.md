# Crypto Monitor (educational)
Project owner: Mayank Joge. Flask backend + vanilla JS/Chart.js frontend. **Educational use only; not financial advice. No predictions are made.**

## Run
```bash
python3 -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export MOCK_MODE=0          # 0 = live CoinGecko (needs internet); 1 = labeled synthetic mock data
python3 app.py              # open http://127.0.0.1:5000
python3 -m unittest discover -s tests -v   # run tests
```
Flask does not auto-load `.env`; export the variables from `.env.example` in your shell. Charts load Chart.js from cdnjs, so the browser needs internet.
Deployment: any host that runs Flask (e.g. `gunicorn app:app`) with env vars set. Not deployed by the author.

## Data source
CoinGecko public API: `GET /coins/markets` (top 50 USD, 24h and 7d change) and `GET /coins/{id}/market_chart?interval=daily` (public tier limited to 365 days of history). The free tier is rate-limited (limits vary); the server caches markets 60s and history 300s (configurable). An optional demo key goes in `COINGECKO_API_KEY`, used server-side only. On HTTP 429 or network failure, cached data is served with a STALE warning; with no cache, an error appears, never a fake price. The Binance fallback was **not** implemented.

## Architecture
`app.py` (routes, cache, stale logic) | `providers.py` (CoinGecko calls, validation, mock data) | `analytics.py` (SMA, volatility, ranking, screen) | `static/` (UI and methodology page) | `tests/`.
The watchlist is stored in the browser's localStorage (no server DB).

## Methods and limitations
See `static/methodology.html`.

## Agent (Run agent button, `/api/agent`)
Rule-based loop, no LLM: (1) observe the market and rank by 24h volume, (2) apply the "deal" rule (7d change <= -5%, volume/market cap >= 0.03, market cap >= $1B), (3) for up to 3 coins run a chronological walk-forward backtest (7-day horizon, 60-point minimum training window) of a 30-day log-linear trend model against naive and 7-day-average baselines, (4) show a forecast with an empirical 10th-90th percentile range **only if** the trend model's error is at least 5% below the best baseline; otherwise it says no forecast is shown. Windows overlap, so the backtest overstates certainty. No trading is performed. Strategy backtesting (fees/drawdown) is not built.

## Hosting (Render, free tier)
Push this folder to a GitHub repo, then on render.com choose New > Blueprint (uses `render.yaml`) or New > Web Service with build `pip install -r requirements.txt` and start `gunicorn app:app --bind 0.0.0.0:$PORT --workers 1`. Set `MOCK_MODE=0`. Free instances sleep after ~15 min idle. Not deployed by the author.
