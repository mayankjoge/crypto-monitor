import os, sys, time, unittest
from unittest import mock
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import analytics, providers, app as appmod
from providers import ProviderError

class Analytics(unittest.TestCase):
    def test_sma(self):
        self.assertEqual(analytics.sma([1, 2, 3, 4, 5], 3), [None, None, 2, 3, 4])
    def test_volatility(self):
        v = analytics.volatility([100, 110, 99, 108.9])  # returns +10%, -10%, +10%
        self.assertAlmostEqual(v, 11.547, places=2)
        self.assertIsNone(analytics.volatility([1, 2]))
    def test_active_and_screen(self):
        cs = [dict(id="a", volume_24h=5, market_cap=100, change_24h=5), dict(id="b", volume_24h=9, market_cap=1000, change_24h=6),
              dict(id="c", volume_24h=None, market_cap=50, change_24h=9), dict(id="d", volume_24h=20, market_cap=100, change_24h=1)]
        self.assertEqual([c["id"] for c in analytics.most_active(cs)], ["d", "b", "a"])
        r = analytics.screen(cs, 3, 0.05, 100)
        self.assertEqual([c["id"] for c in r], ["a"])  # a: turnover .05; b: .009 fails
        r = analytics.screen(cs, 3, 0.005, 100)
        self.assertEqual([c["id"] for c in r], ["a", "b"])  # sorted by turnover desc
class Validation(unittest.TestCase):
    def test_markets(self):
        raw = [dict(id="x", current_price=1, symbol="x"), dict(id="x", current_price=2), dict(id="y", current_price=None),
               dict(id="Bad Id", current_price=1), "junk", dict(id="z", current_price=float("nan")), dict(id="w", current_price=-1)]
        out = providers.validate_markets(raw)
        self.assertEqual([c["id"] for c in out], ["x"]); self.assertIsNone(out[0]["volume_24h"])
        with self.assertRaises(ProviderError): providers.validate_markets({"a": 1})
        with self.assertRaises(ProviderError): providers.validate_markets([])

    def test_negative_optional_market_metrics_become_missing(self):
        result = providers.validate_markets([{
            "id": "neg", "current_price": 1, "total_volume": -2, "market_cap": -3
        }])[0]
        self.assertIsNone(result["volume_24h"])
        self.assertIsNone(result["market_cap"])

    def test_turnover_requires_positive_market_cap(self):
        self.assertIsNone(analytics.turnover({"volume_24h": 3, "market_cap": 0}))
        self.assertIsNone(analytics.turnover({"volume_24h": 3, "market_cap": -1}))
        self.assertAlmostEqual(analytics.turnover({"volume_24h": 5, "market_cap": 100}), 0.05)
    def test_history(self):
        rows = providers.validate_history({"prices": [[2, 5], [1, 4], [1, 4], [3, None]], "total_volumes": [[1, 9]]})
        self.assertEqual(rows, [(1, 4.0, 9.0), (2, 5.0, None)])
        with self.assertRaises(ProviderError): providers.validate_history({})

    def test_malformed_history_rows_are_skipped_not_crashing(self):
        payload = {
            "prices": [None, [], ["bad", 2], [1000, 4], [1000.9, 5], [2000, float("nan")], [3000, 6]],
            "total_volumes": [None, ["no timestamp", 2], [1000, 7], [3000, -1]],
        }
        rows = providers.validate_history(payload)
        self.assertEqual(rows, [(1000, 4.0, 7.0), (3000, 6.0, None)])

    def test_daily_closes_uses_last_sample_per_utc_day(self):
        day = providers.DAY_MS
        rows = [
            (day + 1000, 10.0, 100.0),
            (day + 80_000_000, 11.0, 110.0),
            (2 * day + 1000, 12.0, 120.0),
        ]
        self.assertEqual(providers.daily_closes(rows), [
            (day + 80_000_000, 11.0, 110.0), (2 * day + 1000, 12.0, 120.0)
        ])

    def test_live_history_uses_public_auto_granularity_then_daily_downsamples(self):
        day = providers.DAY_MS
        raw = {
            "prices": [[day + 1000, 10], [day + 40_000_000, 11], [day * 2 + 1000, 12]],
            "total_volumes": [[day + 1000, 100], [day + 40_000_000, 110], [day * 2 + 1000, 120]],
        }
        with mock.patch.object(providers, "_get", return_value=raw) as get:
            rows = providers.live_history("bitcoin", 7)
        get.assert_called_once_with("/coins/bitcoin/market_chart", {"vs_currency": "usd", "days": 37})
        self.assertEqual(rows, [(day + 40_000_000, 11.0, 110.0), (day * 2 + 1000, 12.0, 120.0)])
class Api(unittest.TestCase):
    def setUp(self):
        os.environ["MOCK_MODE"] = "1"; appmod._cache.clear(); self.c = appmod.app.test_client()
    def test_health_endpoint(self):
        self.assertEqual(self.c.get("/api/health").get_json(), {"status": "ok", "mode": "mock"})

    def test_markets_mock(self):
        j = self.c.get("/api/markets").get_json()
        self.assertEqual(j["source"], "mock"); self.assertTrue(len(j["data"]) >= 5)
        for f in ("id", "name", "symbol", "price", "change_24h", "volume_24h", "market_cap"): self.assertIn(f, j["data"][0])
    def test_history_periods(self):
        for d in (7, 30, 90, 365):
            j = self.c.get(f"/api/history/alpha-coin?days={d}").get_json()["data"]
            n = min(d + 1, 365)  # display is capped at one year's worth of daily samples
            self.assertEqual(j["points"], n); self.assertEqual(len(j["sma30"]), n)
            self.assertEqual(len(j["t"]), n)
            if d <= 30 or d >= 90: self.assertIsNotNone(j["sma30"][-1])
    def test_invalid_inputs(self):
        self.assertEqual(self.c.get("/api/history/alpha-coin?days=5").status_code, 400)
        self.assertEqual(self.c.get("/api/history/BAD%20ID?days=7").status_code, 400)
        self.assertEqual(self.c.get("/api/screen?min_turnover=abc").status_code, 400)
        self.assertEqual(self.c.get("/api/screen?min_market_cap=-1").status_code, 400)
        self.assertEqual(self.c.get("/api/screen?min_change_24h=nan").status_code, 400)
        self.assertEqual(self.c.get("/api/screen?min_turnover=inf").status_code, 400)
    def test_screen_matches_rule(self):
        j = self.c.get("/api/screen?min_change_24h=-100&min_turnover=0&min_market_cap=0").get_json()
        self.assertEqual(len(j["data"]), 10); self.assertIn("rule", j)
    def test_active_sorted(self):
        v = [c["volume_24h"] for c in self.c.get("/api/active").get_json()["data"]]
        self.assertEqual(v, sorted(v, reverse=True))
    def test_error_without_cache_and_stale_with_cache(self):
        os.environ["MOCK_MODE"] = "0"; os.environ["CACHE_TTL_MARKETS"] = "0"
        orig = providers.live_markets
        def boom(): raise ProviderError("simulated outage")
        providers.live_markets = boom
        try:
            r = self.c.get("/api/markets"); self.assertEqual(r.status_code, 503); self.assertNotIn("data", r.get_json())
            appmod._cache[("m", "live")] = {"v": providers.mock_markets(), "t": time.time() - 100}
            j = self.c.get("/api/markets").get_json()
            self.assertTrue(j["stale"]); self.assertIn("simulated outage", j["warning"])
        finally:
            providers.live_markets = orig; os.environ.pop("CACHE_TTL_MARKETS"); os.environ["MOCK_MODE"] = "1"
    def test_rate_limit_message(self):
        class R: status_code = 429
        import requests as rq; o = rq.get; rq.get = lambda *a, **k: R()
        try:
            with self.assertRaises(ProviderError) as cm: providers._get("/x", {})
            self.assertIn("rate limit", str(cm.exception))
        finally: rq.get = o
    def test_no_secret_in_static(self):
        d = os.path.join(os.path.dirname(__file__), "..", "static")
        for filename in os.listdir(d):
            path = os.path.join(d, filename)
            if not os.path.isfile(path):
                continue
            with open(path, encoding="utf-8") as handle:
                content = handle.read().lower()
            self.assertNotIn("api_key", content)
            self.assertNotIn("x-cg-", content)
if __name__ == "__main__": unittest.main(verbosity=2)
