"""Pure analytics functions (no I/O) so they are easy to unit test."""
import math

def sma(values, n):
    """Simple moving average; None until n points are available."""
    out = []
    for i in range(len(values)):
        out.append(None if i + 1 < n else sum(values[i + 1 - n:i + 1]) / n)
    return out

def volatility(prices):
    """Sample std-dev of simple daily returns, in percent. None if <3 prices."""
    rets = [(b / a - 1) for a, b in zip(prices, prices[1:]) if a]
    if len(rets) < 2:
        return None
    m = sum(rets) / len(rets)
    return math.sqrt(sum((r - m) ** 2 for r in rets) / (len(rets) - 1)) * 100

def turnover(coin):
    """24h volume / market cap. None if either is missing or cap <= 0."""
    v, c = coin.get("volume_24h"), coin.get("market_cap")
    return v / c if v is not None and c else None

def most_active(coins, limit=10):
    """Ranking rule: descending 24h trading volume. Missing volume excluded."""
    ranked = [c for c in coins if c.get("volume_24h") is not None]
    return sorted(ranked, key=lambda c: c["volume_24h"], reverse=True)[:limit]

def screen(coins, min_change_24h, min_turnover, min_market_cap):
    """'Potential opportunity' screen. A coin passes only if ALL are true:
    24h change >= min_change_24h (%), volume/market-cap >= min_turnover,
    market cap >= min_market_cap (USD). Missing metrics => excluded.
    This flags unusual activity; it does not predict returns."""
    res = []
    for c in coins:
        ch, t, mc = c.get("change_24h"), turnover(c), c.get("market_cap")
        if None in (ch, t, mc):
            continue
        if ch >= min_change_24h and t >= min_turnover and mc >= min_market_cap:
            res.append({**c, "turnover": t})
    return sorted(res, key=lambda c: c["turnover"], reverse=True)

def dip_screen(coins, max_change_7d=-5.0, min_turnover=0.03, min_market_cap=1e9):
    """'Deal candidate' = fell >= 5% in 7d AND active trading AND large cap.
    Means 'cheaper than last week with real volume', NOT undervalued or likely to rebound."""
    res = []
    for c in coins:
        ch, t, mc = c.get("change_7d"), turnover(c), c.get("market_cap")
        if None not in (ch, t, mc) and ch <= max_change_7d and t >= min_turnover and mc >= min_market_cap:
            res.append({**c, "turnover": t})
    return sorted(res, key=lambda c: c["turnover"], reverse=True)

def _trend(train, h, win=30):
    """Linear fit on log-price of the last `win` points, extrapolated h steps."""
    ys = [math.log(p) for p in train[-win:]]
    n = len(ys); mx, my = (n - 1) / 2, sum(ys) / n
    b = sum((x - mx) * (y - my) for x, y in enumerate(ys)) / sum((x - mx) ** 2 for x in range(n))
    return math.exp(my + b * (n - 1 + h - mx))

def walk_forward(prices, h=7, min_train=60):
    """Chronological backtest: at each origin i, only prices[:i+1] are used."""
    rows = []
    for i in range(min_train - 1, len(prices) - h):
        tr = prices[:i + 1]
        rows.append({"i": i, "naive": tr[-1], "ma": sum(tr[-7:]) / 7, "trend": _trend(tr, h), "actual": prices[i + h]})
    return rows

def forecast_backtest(prices, h=7, min_train=60, min_points=30):
    rows = walk_forward(prices, h, min_train)
    if len(rows) < min_points:
        return {"ok": False, "reason": "Not enough history for a reliable backtest; no forecast shown."}
    mape = {k: sum(abs(r[k] - r["actual"]) / r["actual"] for r in rows) / len(rows) * 100 for k in ("naive", "ma", "trend")}
    base = min(mape["naive"], mape["ma"])
    beats = mape["trend"] < 0.95 * base
    lr = sorted(math.log(r["actual"] / r["trend"]) for r in rows)
    q = lambda p: lr[int(p * (len(lr) - 1))]
    out = {"ok": True, "horizon": h, "n_backtest": len(rows), "mape": mape, "beats_baseline": beats, "last_price": prices[-1]}
    if beats:
        pt = _trend(prices, h)
        out["forecast"] = {"point": pt, "low": pt * math.exp(q(.1)), "high": pt * math.exp(q(.9))}
    return out
