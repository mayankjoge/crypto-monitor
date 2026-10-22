"""Rule-based monitoring agent: observe -> screen -> backtest -> report. No LLM, no trading."""
import analytics
from providers import ProviderError

def run_agent(coins, get_prices, horizon=7, max_assets=3):
    steps = []
    act = analytics.most_active(coins, 5)
    steps.append(f"Observed {len(coins)} coins. Most traded (24h volume): " + ", ".join(c["symbol"] for c in act) + ".")
    dips = analytics.dip_screen(coins)
    if dips:
        steps.append(f"Deal rule (7d change <= -5%, volume/market cap >= 0.03, market cap >= $1B) matched {len(dips)}: " + ", ".join(c["symbol"] for c in dips[:5]) + ".")
    else:
        steps.append("Deal rule matched no coins right now; analysing the most traded coins instead.")
    report = []
    for c in (dips or act)[:max_assets]:
        item = {"id": c["id"], "name": c["name"], "symbol": c["symbol"]}
        try:
            fb = analytics.forecast_backtest(get_prices(c["id"]), horizon)
        except ProviderError as e:
            report.append({**item, "error": f"History unavailable: {e}"}); continue
        if not fb["ok"]:
            report.append({**item, "error": fb["reason"]}); continue
        base = min(fb["mape"]["naive"], fb["mape"]["ma"])
        fb["verdict"] = (f"Trend model beat the best baseline in the backtest ({fb['mape']['trend']:.1f}% vs {base:.1f}% error). This is a historical result, not a guarantee."
                         if fb["beats_baseline"] else "Trend model did NOT beat the simple baselines, so no forecast is shown.")
        report.append({**item, **fb})
    steps.append(f"Backtested {len(report)} asset(s) chronologically at a {horizon}-day horizon.")
    return {"steps": steps, "report": report,
            "disclaimer": "Educational only. Forecasts are uncertain, not advice. 'Deal' means a price dip with activity, not undervaluation."}
