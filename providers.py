"""CoinGecko and clearly-labelled deterministic mock data providers."""
import math
import os
import random
import re
import time
from collections.abc import Mapping, Sequence

import requests

BASE = "https://api.coingecko.com/api/v3"
COIN_RE = re.compile(r"^[a-z0-9-]{1,64}$")
PERIODS = {7, 30, 90, 365}
DAY_MS = 86_400_000


class ProviderError(Exception):
    """A safe, user-presentable data provider error."""


def _num(value):
    """Return a finite JSON number as float, otherwise None (bools are not numbers here)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) else None


def validate_markets(raw):
    """Drop malformed/duplicate market rows. Missing optional metrics remain None."""
    if not isinstance(raw, list):
        raise ProviderError("Unexpected markets response shape")

    seen, out = set(), []
    for row in raw:
        if not isinstance(row, Mapping):
            continue
        coin_id = row.get("id")
        price = _num(row.get("current_price"))
        if (
            not isinstance(coin_id, str)
            or not COIN_RE.fullmatch(coin_id)
            or coin_id in seen
            or price is None
            or price <= 0
        ):
            continue

        seen.add(coin_id)
        volume = _num(row.get("total_volume"))
        market_cap = _num(row.get("market_cap"))
        # Invalid negative market metrics are better shown as unavailable than used in ratios.
        if volume is not None and volume < 0:
            volume = None
        if market_cap is not None and market_cap < 0:
            market_cap = None
        updated = row.get("last_updated")
        out.append(
            {
                "id": coin_id,
                "name": str(row.get("name") or coin_id)[:60],
                "symbol": str(row.get("symbol") or "").upper()[:12],
                "price": price,
                "change_24h": _num(row.get("price_change_percentage_24h")),
                "change_7d": _num(row.get("price_change_percentage_7d_in_currency")),
                "volume_24h": volume,
                "market_cap": market_cap,
                "last_updated": updated if isinstance(updated, str) else None,
            }
        )

    if not out:
        raise ProviderError("No valid rows in markets response")
    return out


def validate_history(raw):
    """Validate a CoinGecko history payload; normalize timestamps to integer milliseconds."""
    if not isinstance(raw, Mapping):
        raise ProviderError("Unexpected history response shape")
    prices, volumes = raw.get("prices"), raw.get("total_volumes")
    if not isinstance(prices, list) or not isinstance(volumes, list):
        raise ProviderError("Unexpected history response shape")

    volume_by_time = {}
    for pair in volumes:
        if not isinstance(pair, (list, tuple)) or len(pair) < 2:
            continue
        timestamp, volume = _num(pair[0]), _num(pair[1])
        if timestamp is None or timestamp <= 0:
            continue
        # Normalize before indexing, so fractional and integer timestamps deduplicate correctly.
        key = int(timestamp)
        volume_by_time[key] = volume if volume is not None and volume >= 0 else None

    rows_by_time = {}
    for pair in prices:
        if not isinstance(pair, (list, tuple)) or len(pair) < 2:
            continue
        timestamp, price = _num(pair[0]), _num(pair[1])
        if timestamp is None or timestamp <= 0 or price is None or price <= 0:
            continue
        key = int(timestamp)
        rows_by_time.setdefault(key, (key, price, volume_by_time.get(key)))

    rows = [rows_by_time[key] for key in sorted(rows_by_time)]
    if len(rows) < 2:
        raise ProviderError("Insufficient valid history data")
    return rows


def daily_closes(rows):
    """Reduce intraday observations to the final observed price/volume for each UTC day."""
    by_day = {}
    for timestamp, price, volume in rows:
        day = int(timestamp) // DAY_MS
        previous = by_day.get(day)
        if previous is None or timestamp >= previous[0]:
            by_day[day] = (timestamp, price, volume)
    daily = [by_day[day] for day in sorted(by_day)]
    if len(daily) < 2:
        raise ProviderError("Insufficient daily history data")
    return daily


def _get(path, params):
    headers = {"accept": "application/json"}
    key = os.getenv("COINGECKO_API_KEY", "").strip()
    if key and key != "your_demo_key_here":
        headers["x-cg-demo-api-key"] = key
    try:
        response = requests.get(BASE + path, params=params, headers=headers, timeout=12)
    except requests.RequestException as exc:
        raise ProviderError(f"Network error: {type(exc).__name__}") from None

    if response.status_code == 429:
        raise ProviderError("CoinGecko rate limit reached (HTTP 429)")
    if response.status_code in (401, 403):
        raise ProviderError("CoinGecko authorization failed; check the optional API key")
    if response.status_code != 200:
        raise ProviderError(f"CoinGecko returned HTTP {response.status_code}")
    try:
        return response.json()
    except (ValueError, requests.exceptions.JSONDecodeError):
        raise ProviderError("Malformed JSON from CoinGecko") from None


def live_markets():
    return validate_markets(
        _get(
            "/coins/markets",
            {
                "vs_currency": "usd",
                "order": "market_cap_desc",
                "per_page": 50,
                "page": 1,
                "price_change_percentage": "24h,7d",
            },
        )
    )


def live_history(coin_id, days):
    """Fetch a warm-up window and downsample public API observations to daily closes.

    CoinGecko's public API chooses chart granularity automatically. For 2–90 day
    ranges it can return hourly observations, so passing ``interval=daily`` is
    intentionally avoided; using the latest observation of each UTC day keeps
    SMA and volatility calculations on daily data.
    """
    request_days = min(days + 30, 365)
    payload = _get(
        f"/coins/{coin_id}/market_chart",
        {"vs_currency": "usd", "days": request_days},
    )
    return daily_closes(validate_history(payload))


# ---- MOCK (NOT real market data) ----
_MOCK = [
    ("alpha-coin", "Alpha Coin", "ALP", 52000),
    ("beta-token", "Beta Token", "BTA", 2400),
    ("gamma-cash", "Gamma Cash", "GMC", 310),
    ("delta-net", "Delta Net", "DLT", 95),
    ("epsilon-pay", "Epsilon Pay", "EPS", 1.2),
    ("zeta-chain", "Zeta Chain", "ZTC", 0.45),
    ("eta-swap", "Eta Swap", "ETA", 14),
    ("theta-fi", "Theta Fi", "THF", 6.5),
    ("iota-link", "Iota Link", "IOL", 22),
    ("kappa-dao", "Kappa DAO", "KPD", 0.08),
]


def _walk(coin_id, count):
    randomizer = random.Random(coin_id)
    base = next(base for cid, _, _, base in _MOCK if cid == coin_id)
    price, out = base, []
    for _ in range(count):
        price *= 1 + randomizer.gauss(0.0005, 0.03)
        out.append((price, base * 1e5 * (1 + randomizer.random())))
    return out


def mock_markets():
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    raw = []
    for index, (coin_id, name, symbol, _) in enumerate(_MOCK):
        history = _walk(coin_id, 31)
        raw.append(
            {
                "id": coin_id,
                "name": name,
                "symbol": symbol.lower(),
                "current_price": history[-1][0],
                "price_change_percentage_24h": (history[-1][0] / history[-2][0] - 1) * 100,
                "price_change_percentage_7d_in_currency": (history[-1][0] / history[-8][0] - 1) * 100,
                "total_volume": history[-1][1] * 50,
                "market_cap": history[-1][1] * 50 * (3 + index * 4) * 10,
                "last_updated": now,
            }
        )
    return validate_markets(raw)


def mock_history(coin_id, days):
    if coin_id not in {item[0] for item in _MOCK}:
        raise ProviderError("Unknown mock coin")
    count = min(days + 30, 365)
    end = int(time.time() // 86400 * 86400) * 1000
    walk = _walk(coin_id, count)
    payload = {
        "prices": [
            [end - (count - 1 - index) * DAY_MS, price]
            for index, (price, _) in enumerate(walk)
        ],
        "total_volumes": [
            [end - (count - 1 - index) * DAY_MS, volume]
            for index, (_, volume) in enumerate(walk)
        ],
    }
    return validate_history(payload)
