"""Flask API and static app for the educational Crypto Monitor."""
import datetime
import os
import threading
import time

from flask import Flask, jsonify, request

import analytics
import providers
from providers import ProviderError

app = Flask(__name__, static_folder="static", static_url_path="")
_cache = {}
_cache_lock = threading.Lock()


def mock_on():
    return os.getenv("MOCK_MODE", "0").strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name, default, minimum=0):
    try:
        return max(minimum, int(os.getenv(name, str(default))))
    except (TypeError, ValueError, OverflowError):
        return default


def cached(key, ttl, fetch):
    """Return (value, fetched_at, error), falling back to old cached data on provider errors."""
    now = time.time()
    with _cache_lock:
        entry = _cache.get(key)
    if entry and now - entry["t"] < max(0, ttl):
        return entry["v"], entry["t"], None

    try:
        value = fetch()
    except ProviderError as exc:
        if entry:
            return entry["v"], entry["t"], str(exc)
        raise

    fetched_at = time.time()
    with _cache_lock:
        _cache[key] = {"v": value, "t": fetched_at}
    return value, fetched_at, None


def envelope(data, fetched_at, error, **extra):
    age = max(0, time.time() - fetched_at)
    stale = error is not None or age > _env_int("STALE_AFTER_SECONDS", 600)
    warning = f"Showing cached data; refresh failed: {error}" if error else None
    return jsonify(
        {
            "data": data,
            "source": "mock" if mock_on() else "coingecko",
            "fetched_at": datetime.datetime.fromtimestamp(
                fetched_at, datetime.timezone.utc
            ).isoformat(),
            "stale": stale,
            "warning": warning,
            **extra,
        }
    )


def markets():
    mode = "mock" if mock_on() else "live"
    fetch = providers.mock_markets if mock_on() else providers.live_markets
    return cached(("m", mode), _env_int("CACHE_TTL_MARKETS", 60), fetch)


@app.errorhandler(ProviderError)
def provider_err(error):
    return (
        jsonify({"error": str(error), "source": "mock" if mock_on() else "coingecko"}),
        503,
    )


@app.get("/api/health")
def api_health():
    return jsonify({"status": "ok", "mode": "mock" if mock_on() else "live"})


@app.get("/api/markets")
def api_markets():
    data, fetched_at, error = markets()
    return envelope(data, fetched_at, error)


@app.get("/api/active")
def api_active():
    data, fetched_at, error = markets()
    return envelope(
        analytics.most_active(data, 10),
        fetched_at,
        error,
        rule="Ranked by 24h trading volume (USD), descending",
    )


def _f(name, default, lower, upper):
    try:
        value = float(request.args.get(name, default))
    except (TypeError, ValueError, OverflowError):
        raise ValueError(f"{name} must be a number") from None
    if not (lower <= value <= upper):
        raise ValueError(f"{name} must be between {lower} and {upper}")
    return value


@app.get("/api/screen")
def api_screen():
    try:
        min_change = _f("min_change_24h", 3, -100, 1000)
        min_turnover = _f("min_turnover", 0.05, 0, 100)
        min_market_cap = _f("min_market_cap", 1e9, 0, 1e15)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    data, fetched_at, error = markets()
    rule = (
        f"24h change >= {min_change:g}% AND 24h volume / market cap >= "
        f"{min_turnover:g} AND market cap >= ${min_market_cap:,.0f}"
    )
    return envelope(
        analytics.screen(data, min_change, min_turnover, min_market_cap),
        fetched_at,
        error,
        rule=rule,
    )


@app.get("/api/history/<coin_id>")
def api_history(coin_id):
    try:
        days = int(request.args.get("days", 30))
    except (TypeError, ValueError, OverflowError):
        days = -1
    if not providers.COIN_RE.fullmatch(coin_id) or days not in providers.PERIODS:
        return jsonify({"error": "Invalid coin id or period (allowed: 7, 30, 90, 365)"}), 400

    is_mock = mock_on()
    fetch = (
        (lambda: providers.mock_history(coin_id, days))
        if is_mock
        else (lambda: providers.live_history(coin_id, days))
    )
    rows, fetched_at, error = cached(
        ("h", is_mock, coin_id, days), _env_int("CACHE_TTL_HISTORY", 300), fetch
    )

    prices = [row[1] for row in rows]
    sma7 = analytics.sma(prices, 7)
    sma30 = analytics.sma(prices, 30)
    visible_count = min(days + 1, 365)
    start = slice(-visible_count, None)
    visible_prices = prices[start]
    visible_timestamps = [row[0] for row in rows][start]
    visible_volumes = [row[2] for row in rows][start]
    output = {
        "t": visible_timestamps,
        "price": visible_prices,
        "volume": visible_volumes,
        "sma7": sma7[start],
        "sma30": sma30[start],
        "volatility_pct": analytics.volatility(visible_prices),
        "points": len(visible_prices),
        "last_point_ts": visible_timestamps[-1],
    }
    return envelope(output, fetched_at, error)


@app.get("/")
def index():
    return app.send_static_file("index.html")


if __name__ == "__main__":
    app.run(host=os.getenv("HOST", "127.0.0.1"), port=_env_int("PORT", 5000, 1))
