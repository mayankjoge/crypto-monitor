import os, sys, time, unittest
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
class Forecast(unittest.TestCase):
    def test_no_leakage(self):
        import random; r = random.Random(1); p = [100.0]
        for _ in range(150): p.append(p[-1] * (1 + r.gauss(0, .02)))
        q = p[:-10] + [1.0] * 10  # corrupt the final 10 "future" values
        a, b = analytics.walk_forward(p), analytics.walk_forward(q)
        for x, y in zip(a, b):
            if x["i"] + 7 < len(p) - 10: self.assertEqual((x["naive"], x["ma"], x["trend"]), (y["naive"], y["ma"], y["trend"]))
    def test_trend_wins_on_exponential_and_insufficient(self):
        p = [100 * 1.01 ** i for i in range(150)]
        fb = analytics.forecast_backtest(p); self.assertTrue(fb["beats_baseline"]); self.assertIn("forecast", fb)
        self.assertFalse(analytics.forecast_backtest(p[:50])["ok"])
    def test_agent_endpoint(self):
        os.environ["MOCK_MODE"] = "1"; appmod._cache.clear()
        j = appmod.app.test_client().get("/api/agent").get_json()
        self.assertEqual(j["source"], "mock"); self.assertTrue(j["data"]["report"]); self.assertIn("disclaimer", j["data"])
        for r in j["data"]["report"]: self.assertTrue(("forecast" in r) == r.get("beats_baseline", False))
class Validation(unittest.TestCase):
    def test_markets(self):
        raw = [dict(id="x", current_price=1, symbol="x"), dict(id="x", current_price=2), dict(id="y", current_price=None),
               dict(id="Bad Id", current_price=1), "junk", dict(id="z", current_price=float("nan")), dict(id="w", current_price=-1)]
        out = providers.validate_markets(raw)
        self.assertEqual([c["id"] for c in out], ["x"]); self.assertIsNone(out[0]["volume_24h"])
        with self.assertRaises(ProviderError): providers.validate_markets({"a": 1})
        with self.assertRaises(ProviderError): providers.validate_markets([])
    def test_history(self):
        rows = providers.validate_history({"prices": [[2, 5], [1, 4], [1, 4], [3, None]], "total_volumes": [[1, 9]]})
        self.assertEqual(rows, [(1, 4.0, 9.0), (2, 5.0, None)])
        with self.assertRaises(ProviderError): providers.validate_history({})
class Api(unittest.TestCase):
    def setUp(self):
        os.environ["MOCK_MODE"] = "1"; appmod._cache.clear(); self.c = appmod.app.test_client()
    def test_markets_mock(self):
        j = self.c.get("/api/markets").get_json()
        self.assertEqual(j["source"], "mock"); self.assertTrue(len(j["data"]) >= 5)
        for f in ("id", "name", "symbol", "price", "change_24h", "volume_24h", "market_cap"): self.assertIn(f, j["data"][0])
    def test_history_periods(self):
        for d in (7, 30, 90, 365):
            j = self.c.get(f"/api/history/alpha-coin?days={d}").get_json()["data"]
            n = min(d + 1, 365)  # fetch capped at 365 points (public API limit)
            self.assertEqual(j["points"], n); self.assertEqual(len(j["sma30"]), n)
            if d >= 90: self.assertIsNotNone(j["sma30"][-1])
    def test_invalid_inputs(self):
        self.assertEqual(self.c.get("/api/history/alpha-coin?days=5").status_code, 400)
        self.assertEqual(self.c.get("/api/history/BAD%20ID?days=7").status_code, 400)
        self.assertEqual(self.c.get("/api/screen?min_turnover=abc").status_code, 400)
        self.assertEqual(self.c.get("/api/screen?min_market_cap=-1").status_code, 400)
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
        for f in os.listdir(d):
            t = open(os.path.join(d, f)).read().lower(); self.assertNotIn("api_key", t); self.assertNotIn("x-cg-", t)
if __name__ == "__main__": unittest.main(verbosity=2)
