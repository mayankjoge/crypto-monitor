import os, time, datetime
from flask import Flask, jsonify, request
import analytics, providers, agent
from providers import ProviderError

app = Flask(__name__, static_folder="static", static_url_path="")
_cache = {}

def mock_on():
    return os.getenv("MOCK_MODE", "0") == "1"

def cached(key, ttl, fetch):
    """Return (value, fetched_at, error). On fetch failure serve old cache (marked stale) or raise."""
    now, e = time.time(), _cache.get(key)
    if e and now - e["t"] < ttl:
        return e["v"], e["t"], None
    try:
        v = fetch()
        _cache[key] = {"v": v, "t": now}
        return v, now, None
    except ProviderError as ex:
        if e:
            return e["v"], e["t"], str(ex)
        raise

def envelope(data, t, err, **extra):
    age = time.time() - t
    stale = err is not None or age > int(os.getenv("STALE_AFTER_SECONDS", 600))
    return jsonify({"data": data, "source": "mock" if mock_on() else "coingecko",
        "fetched_at": datetime.datetime.fromtimestamp(t, datetime.timezone.utc).isoformat(),
        "stale": stale, "warning": (f"Showing cached data; refresh failed: {err}" if err else None), **extra})

def markets():
    mode = "mock" if mock_on() else "live"
    fn = providers.mock_markets if mock_on() else providers.live_markets
    return cached(("m", mode), int(os.getenv("CACHE_TTL_MARKETS", 60)), fn)

@app.errorhandler(ProviderError)
def provider_err(e):
    return jsonify({"error": str(e), "source": "mock" if mock_on() else "coingecko"}), 503

@app.get("/api/markets")
def api_markets():
    d, t, err = markets()
    return envelope(d, t, err)

@app.get("/api/active")
def api_active():
    d, t, err = markets()
    return envelope(analytics.most_active(d, 10), t, err, rule="Ranked by 24h trading volume (USD), descending")

def _f(name, default, lo, hi):
    try:
        v = float(request.args.get(name, default))
    except ValueError:
        raise ValueError(f"{name} must be a number")
    if not lo <= v <= hi:
        raise ValueError(f"{name} must be between {lo} and {hi}")
    return v

@app.get("/api/screen")
def api_screen():
    try:
        ch, tu, mc = _f("min_change_24h", 3, -100, 1000), _f("min_turnover", 0.05, 0, 100), _f("min_market_cap", 1e9, 0, 1e15)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    d, t, err = markets()
    rule = f"24h change >= {ch}% AND 24h volume / market cap >= {tu} AND market cap >= ${mc:,.0f}"
    return envelope(analytics.screen(d, ch, tu, mc), t, err, rule=rule)

@app.get("/api/history/<coin_id>")
def api_history(coin_id):
    try:
        days = int(request.args.get("days", 30))
    except ValueError:
        days = -1
    if not providers.COIN_RE.match(coin_id) or days not in providers.PERIODS:
        return jsonify({"error": "Invalid coin id or period (allowed: 7, 30, 90, 365)"}), 400
    fn = (lambda: providers.mock_history(coin_id, days)) if mock_on() else (lambda: providers.live_history(coin_id, days))
    rows, t, err = cached(("h", mock_on(), coin_id, days), int(os.getenv("CACHE_TTL_HISTORY", 300)), fn)
    prices = [r[1] for r in rows]
    s7, s30 = analytics.sma(prices, 7), analytics.sma(prices, 30)
    k = slice(-(days + 1), None)
    out = {"t": [r[0] for r in rows][k], "price": prices[k], "volume": [r[2] for r in rows][k],
           "sma7": s7[k], "sma30": s30[k], "volatility_pct": analytics.volatility(prices[k]),
           "points": len(prices[k]), "last_point_ts": rows[-1][0]}
    return envelope(out, t, err)

def get_prices(cid):
    fn = (lambda: providers.mock_history(cid, 365)) if mock_on() else (lambda: providers.live_history(cid, 365))
    rows, _, _ = cached(("h", mock_on(), cid, 365), int(os.getenv("CACHE_TTL_HISTORY", 300)), fn)
    return [r[1] for r in rows]

@app.get("/api/agent")
def api_agent():
    d, t, err = markets()
    return envelope(agent.run_agent(d, get_prices), t, err)

@app.get("/")
def index():
    return app.send_static_file("index.html")

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", 5000)))
