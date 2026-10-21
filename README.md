# Crypto Monitor (educational)

A small Flask + vanilla JavaScript crypto-market dashboard. It includes searchable/sortable market data, a browser-local watchlist, gainers/losers filters, daily price history with moving averages, activity ranking, and a configurable metrics screen.

**Educational use only. This is not financial advice. No forecasts are made.** Live data comes from CoinGecko; mock mode uses synthetic, clearly-labelled values.

## Requirements

- Python 3.10 or later
- Internet access for live CoinGecko data (and only if you want to load live data)
- A modern browser with Canvas support; charts use built-in Canvas and do not require a chart-library CDN

## Run locally

Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
MOCK_MODE=1 python app.py
```

Windows PowerShell:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:MOCK_MODE = "1"
python app.py
```

Open <http://127.0.0.1:5000>. `MOCK_MODE=1` is the recommended first run and works without CoinGecko access. Mock values are not real prices. For live data, set `MOCK_MODE=0` (or unset it) and run the app again. CoinGecko's public API may rate-limit anonymous requests; an optional demo key can be configured server-side using `COINGECKO_API_KEY`.

The Flask app reads environment variables directly; it does not auto-load `.env`. You can copy `.env.example` and export values in your shell. Never place API credentials in files under `static/` or share them in screenshots.

## Tests

Run the offline test suite from the project root:

```bash
python -m unittest discover -s tests -v
```

Basic smoke checks after startup:

```bash
curl http://127.0.0.1:5000/api/health
curl http://127.0.0.1:5000/api/markets
curl 'http://127.0.0.1:5000/api/history/alpha-coin?days=30'
```

## Configuration

| Variable | Default | Purpose |
|---|---:|---|
| `MOCK_MODE` | `0` | `1` selects synthetic demonstration data; otherwise use CoinGecko |
| `PORT` | `5000` | Local HTTP port |
| `HOST` | `127.0.0.1` | Listening interface; use `0.0.0.0` only when intentionally exposing the server |
| `COINGECKO_API_KEY` | empty | Optional CoinGecko Demo API key; remains on the server |
| `CACHE_TTL_MARKETS` | `60` | Market data cache lifetime in seconds |
| `CACHE_TTL_HISTORY` | `300` | History cache lifetime in seconds |
| `STALE_AFTER_SECONDS` | `600` | Age after which cached data is marked stale |

## Architecture

- `app.py`: Flask routes, validation of query parameters, in-memory caching and stale-data responses
- `providers.py`: CoinGecko transport/validation, UTC daily downsampling and deterministic mock data
- `analytics.py`: moving averages, volatility, activity ranking and screening rules
- `static/`: dashboard, CSS, canvas chart renderer and methodology page
- `tests/`: offline unit and API regression tests

The watchlist is stored in the browser's local storage; there is no user account or server-side database. Cache values are process-local and reset when the server restarts. History is limited to one year. Forecasting, predictive modelling, backtesting, and provider fallback are not implemented.
