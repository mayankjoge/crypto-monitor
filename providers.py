"""Data providers + validation. Live = CoinGecko public API. Mock = deterministic, labeled."""
import os, re, random, time, math
import requests

BASE = "https://api.coingecko.com/api/v3"
COIN_RE = re.compile(r"^[a-z0-9-]{1,64}$")
PERIODS = {7, 30, 90, 365}

class ProviderError(Exception):
    pass

def _num(x):
    return float(x) if isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) else None

def validate_markets(raw):
    """Drop malformed rows and duplicates; missing optional fields become None."""
    if not isinstance(raw, list):
        raise ProviderError("Unexpected markets response shape")
    seen, out = set(), []
    for r in raw:
        if not isinstance(r, dict):
            continue
        cid, price = r.get("id"), _num(r.get("current_price"))
        if not isinstance(cid, str) or not COIN_RE.match(cid) or cid in seen or price is None or price <= 0:
            continue
        seen.add(cid)
        out.append({"id": cid, "name": str(r.get("name") or cid)[:60],
                    "symbol": str(r.get("symbol") or "").upper()[:12], "price": price,
                    "change_24h": _num(r.get("price_change_percentage_24h")),
                    "change_7d": _num(r.get("price_change_percentage_7d_in_currency")),
                    "volume_24h": _num(r.get("total_volume")), "market_cap": _num(r.get("market_cap")),
                    "last_updated": r.get("last_updated") if isinstance(r.get("last_updated"), str) else None})
    if not out:
        raise ProviderError("No valid rows in markets response")
    return out

def validate_history(raw):
    try:
        prices, vols = raw["prices"], raw["total_volumes"]
    except (TypeError, KeyError):
        raise ProviderError("Unexpected history response shape")
    vmap = {int(t): _num(v) for t, v in vols if isinstance(t, (int, float))}
    seen, rows = set(), []
    for t, p in prices:
        p = _num(p)
        if p is None or p <= 0 or t in seen:
            continue
        seen.add(t)
        rows.append((int(t), p, vmap.get(int(t))))
    rows.sort()
    if len(rows) < 2:
        raise ProviderError("Insufficient history")
    return rows

def _get(path, params):
    headers = {}
    key = os.getenv("COINGECKO_API_KEY", "")
    if key and key != "your_demo_key_here":
        headers["x-cg-demo-api-key"] = key
    try:
        r = requests.get(BASE + path, params=params, headers=headers, timeout=10)
    except requests.RequestException as e:
        raise ProviderError(f"Network error: {type(e).__name__}")
    if r.status_code == 429:
        raise ProviderError("CoinGecko rate limit reached (HTTP 429)")
    if r.status_code != 200:
        raise ProviderError(f"CoinGecko returned HTTP {r.status_code}")
    try:
        return r.json()
    except ValueError:
        raise ProviderError("Malformed JSON from CoinGecko")

def live_markets():
    return validate_markets(_get("/coins/markets", {"vs_currency": "usd", "order": "market_cap_desc",
        "per_page": 50, "page": 1, "price_change_percentage": "24h,7d"}))

def live_history(coin_id, days):
    return validate_history(_get(f"/coins/{coin_id}/market_chart",
        {"vs_currency": "usd", "days": min(days + 30, 365), "interval": "daily"}))

# ---- MOCK (NOT real market data) ----
_MOCK = [("alpha-coin","Alpha Coin","ALP",52000),("beta-token","Beta Token","BTA",2400),("gamma-cash","Gamma Cash","GMC",310),
 ("delta-net","Delta Net","DLT",95),("epsilon-pay","Epsilon Pay","EPS",1.2),("zeta-chain","Zeta Chain","ZTC",0.45),
 ("eta-swap","Eta Swap","ETA",14),("theta-fi","Theta Fi","THF",6.5),("iota-link","Iota Link","IOL",22),("kappa-dao","Kappa DAO","KPD",0.08)]

def _walk(cid, n):
    rnd = random.Random(cid)
    base = next(b for i, _, _, b in _MOCK if i == cid)
    p, out = base, []
    for _ in range(n):
        p *= 1 + rnd.gauss(0.0005, 0.03)
        out.append((p, base * 1e5 * (1 + rnd.random())))
    return out

def mock_markets():
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    raw = []
    for i, (cid, name, sym, _) in enumerate(_MOCK):
        w = _walk(cid, 31)
        raw.append({"id": cid, "name": name, "symbol": sym.lower(), "current_price": w[-1][0],
            "price_change_percentage_24h": (w[-1][0] / w[-2][0] - 1) * 100,
            "price_change_percentage_7d_in_currency": (w[-1][0] / w[-8][0] - 1) * 100,
            "total_volume": w[-1][1] * 50, "market_cap": w[-1][1] * 50 * (3 + i * 4) * 10, "last_updated": now})
    return validate_markets(raw)

def mock_history(cid, days):
    if cid not in {m[0] for m in _MOCK}:
        raise ProviderError("Unknown mock coin")
    n = min(days + 30, 365)
    end = int(time.time() // 86400 * 86400) * 1000
    w = _walk(cid, n)
    return validate_history({"prices": [[end - (n - 1 - i) * 86400000, p] for i, (p, _) in enumerate(w)],
                             "total_volumes": [[end - (n - 1 - i) * 86400000, v] for i, (_, v) in enumerate(w)]})
