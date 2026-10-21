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
    """24h volume / market cap. None if metrics are missing or invalid."""
    v, c = coin.get("volume_24h"), coin.get("market_cap")
    valid_v = isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and v >= 0
    valid_c = isinstance(c, (int, float)) and not isinstance(c, bool) and math.isfinite(c) and c > 0
    return v / c if valid_v and valid_c else None

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
