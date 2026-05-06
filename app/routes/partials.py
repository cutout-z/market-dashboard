"""HTMX partial endpoints — one per dashboard panel."""

import time
from datetime import datetime, timedelta
from pathlib import Path

import re
import urllib.parse

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.sources.shocks import HistoricalShocksSource, ShockAnalogMatcher
from app.sources.indices import IndicesSource
from app.sources.futures import FuturesSource
from app.sources.forex import ForexSource
from app.sources.bonds import BondsSource
from app.sources.economy_live import EconomyLiveSource
from app.sources.polymarket import PolymarketSource
from app.sources.news import NewsSource
from app.sources.pulse import PulseSource
from app.sources.calendar import CalendarSource
from app.sources.movers import MoversSource
from app.sources.fred import FredYieldSource, FredEconomySource
from app.sources.options import OptionsSkewSource
from app.sources.commodities import CommoditiesSource
from app.config import COMMODITY_LOOKUP, COMMODITY_NOTES_DIR
from app.sources.intl_bonds import IntlBondsSource
from app.sources.mag7 import Mag7Source
from app.sources.earnings import EarningsSource
from app.sources.fedwatch import FedWatchSource
from app.sources.cot import COTSource
from app.sources.economy_historical import EconomyHistoricalSource

router = APIRouter(prefix="/partials")
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))

# Source instances (shared with main.py via module-level refs)
indices_source = IndicesSource()
futures_source = FuturesSource()
forex_source = ForexSource()
bonds_source = BondsSource()
economy_source = EconomyLiveSource()
polymarket_source = PolymarketSource()
news_source = NewsSource()
pulse_source = PulseSource()
calendar_source = CalendarSource()
movers_source = MoversSource()
fred_yield_source = FredYieldSource()
fred_economy_source = FredEconomySource()
options_skew_source = OptionsSkewSource()
commodities_source = CommoditiesSource()
intl_bonds_source = IntlBondsSource()
mag7_source = Mag7Source()
earnings_source = EarningsSource()
fedwatch_source = FedWatchSource()
cot_source = COTSource()
economy_historical_source = EconomyHistoricalSource()
shocks_source = HistoricalShocksSource()
ALL_SOURCES = [
    indices_source, futures_source, forex_source, bonds_source,
    economy_source, polymarket_source, news_source, pulse_source,
    calendar_source, movers_source, fred_yield_source, fred_economy_source,
    options_skew_source, commodities_source, intl_bonds_source, mag7_source,
    earnings_source, fedwatch_source, cot_source, economy_historical_source,
    shocks_source,
]


# ─── Indices ───
@router.get("/indices", response_class=HTMLResponse)
async def partial_indices(request: Request, spark_period: str = "1W"):
    data = indices_source.get_cached() or {"world": [], "sectors": [], "defense": []}
    return templates.TemplateResponse(request, "partials/indices.html", {
        "world": data.get("world", []),
        "sectors": data.get("sectors", []),
        "defense": data.get("defense", []),
        "sector_treemap": data.get("sector_treemap", []),
        "spark_period": spark_period,
    })


# ─── Futures ───
@router.get("/futures", response_class=HTMLResponse)
async def partial_futures(request: Request, spark_period: str = "1W"):
    data = futures_source.get_cached() or {"categories": {}}
    return templates.TemplateResponse(request, "partials/futures.html", {
        "categories": data.get("categories", {}),
        "spark_period": spark_period,
    })


# ─── Forex ───
@router.get("/forex-pairs", response_class=HTMLResponse)
async def partial_forex_pairs(request: Request):
    data = forex_source.get_cached() or {"pairs": []}
    return templates.TemplateResponse(request, "partials/forex_pairs.html", {
        "pairs": data.get("pairs", []),
    })


@router.get("/forex-heatmap", response_class=HTMLResponse)
async def partial_forex_heatmap(request: Request, period: str = "1D"):
    data = forex_source.get_cached() or {"heatmaps": {}}
    heatmaps = data.get("heatmaps", {})
    hm = heatmaps.get(period, {"currencies": [], "matrix": []})
    return templates.TemplateResponse(request, "partials/forex_heatmap.html", {
        "currencies": hm.get("currencies", []),
        "matrix": hm.get("matrix", []),
        "period": period,
    })


@router.get("/forex-correlations", response_class=HTMLResponse)
async def partial_forex_correlations(request: Request):
    data = forex_source.get_cached() or {}
    corr = data.get("correlations", {"labels": [], "matrix": []})
    return templates.TemplateResponse(request, "partials/forex_correlations.html", {
        "labels": corr.get("labels", []),
        "matrix": corr.get("matrix", []),
    })


# ─── Bonds ───
@router.get("/bonds", response_class=HTMLResponse)
async def partial_bonds(request: Request):
    # Prefer FRED data (full curve), fall back to yfinance
    fred = fred_yield_source.get_cached() or {}
    yf_data = bonds_source.get_cached() or {}

    # Use FRED yield curve if available, otherwise yfinance
    if fred.get("yields"):
        us_yields = fred["yields"]
        yield_curve = fred.get("yield_curve", {"maturities": [], "yields": [], "labels": []})
        spread_2s10s = fred.get("spread_2s10s")
        spread_3m10y = fred.get("spread_3m10y")
        real_rate = fred.get("real_rate")
        breakevens = fred.get("breakevens", [])
    else:
        us_yields = yf_data.get("us_yields", [])
        yield_curve = yf_data.get("yield_curve", {"maturities": [], "yields": [], "labels": []})
        spread_2s10s = yf_data.get("spread_2s10s")
        spread_3m10y = yf_data.get("spread_3m10y")
        real_rate = yf_data.get("real_rate")
        breakevens = []

    # International yields from central bank sources
    intl = intl_bonds_source.get_cached() or {}

    return templates.TemplateResponse(request, "partials/bonds.html", {
        "us_yields": us_yields,
        "yield_curve": yield_curve,
        "spread_2s10s": spread_2s10s,
        "spread_3m10y": spread_3m10y,
        "spread_2s30s": fred.get("spread_2s30s"),
        "move": yf_data.get("move"),
        "real_rate": real_rate,
        "breakevens": breakevens,
        "credit_spreads": fred.get("credit_spreads", []),
        "au_yields": intl.get("au_yields", []),
        "au_curve": intl.get("au_curve", {"maturities": [], "yields": [], "labels": []}),
        "au_spreads": intl.get("au_spreads", []),
        "jp_yields": intl.get("jp_yields", []),
        "jp_curve": intl.get("jp_curve", {"maturities": [], "yields": [], "labels": []}),
        "jp_spreads": intl.get("jp_spreads", []),
        "euro_yields": intl.get("euro_yields", []),
        "euro_curve": intl.get("euro_curve", {"maturities": [], "yields": [], "labels": []}),
        "euro_spreads": intl.get("euro_spreads", []),
        "uk_yields": intl.get("uk_yields", []),
        "uk_curve": intl.get("uk_curve", {"maturities": [], "yields": [], "labels": []}),
        "uk_spreads": intl.get("uk_spreads", []),
        "data_source": "FRED" if fred.get("yields") else "yfinance",
    })


# ─── Economy ───
@router.get("/economy", response_class=HTMLResponse)
async def partial_economy(request: Request):
    # Reference data (static)
    ref_data = economy_source.get_cached() or {"rows": [], "indicators": [], "countries": []}
    # Live FRED indicators
    fred_data = fred_economy_source.get_cached() or {"indicators": []}

    return templates.TemplateResponse(request, "partials/economy.html", {
        "rows": ref_data.get("rows", []),
        "indicators": ref_data.get("indicators", []),
        "fred_indicators": fred_data.get("indicators", []),
        "nowcasts": fred_data.get("nowcasts", []),
        "cb_rates": fred_data.get("cb_rates", []),
    })


@router.get("/economy-historical", response_class=HTMLResponse)
async def partial_economy_historical(request: Request):
    data = economy_historical_source.get_cached() or {"charts": []}
    return templates.TemplateResponse(request, "partials/economy_historical.html", {
        "charts": data.get("charts", []),
    })


# ─── News ───
@router.get("/polymarket", response_class=HTMLResponse)
async def partial_polymarket(request: Request):
    data = polymarket_source.get_cached() or {"items": []}
    return templates.TemplateResponse(request, "partials/polymarket.html", {
        "items": data.get("items", []),
        "error": data.get("error"),
    })


@router.get("/news-feed", response_class=HTMLResponse)
async def partial_news_feed(request: Request):
    data = news_source.get_cached() or {"items": []}
    return templates.TemplateResponse(request, "partials/news_feed.html", {
        "items": data.get("items", []),
    })


@router.get("/calendar", response_class=HTMLResponse)
async def partial_calendar(request: Request):
    data = calendar_source.get_cached() or {"events": []}
    return templates.TemplateResponse(request, "partials/calendar.html", {
        "events": data.get("events", []),
        "error": data.get("error"),
    })


@router.get("/movers", response_class=HTMLResponse)
async def partial_movers(request: Request, region: str = "US"):
    from app.config import MOVERS_EXCHANGES
    data = movers_source.get_cached() or {}
    if region not in MOVERS_EXCHANGES:
        region = "US"
    region_data = data.get(region, {})
    return templates.TemplateResponse(request, "partials/movers.html", {
        "gainers": region_data.get("gainers", []),
        "losers": region_data.get("losers", []),
        "active": region_data.get("active", []),
        "region": region,
        "regions": MOVERS_EXCHANGES,
    })


# ─── Macro Pulse ───
@router.get("/pulse-hud", response_class=HTMLResponse)
async def partial_pulse_hud(request: Request):
    data = pulse_source.get_cached() or {}
    # Prefer FRED for spreads, fall back to yfinance bonds
    fred = fred_yield_source.get_cached() or {}
    bonds_data = bonds_source.get_cached() or {}
    return templates.TemplateResponse(request, "partials/pulse_hud.html", {
        "hud": data.get("hud", []),
        "ratios": data.get("ratios", []),
        "spread_2s10s": fred.get("spread_2s10s") or bonds_data.get("spread_2s10s"),
        "move": bonds_data.get("move"),
        "real_rate": fred.get("real_rate"),
        "credit_spreads": fred.get("credit_spreads", []),
    })


@router.get("/pulse-rotation", response_class=HTMLResponse)
async def partial_pulse_rotation(request: Request):
    data = pulse_source.get_cached() or {}
    return templates.TemplateResponse(request, "partials/pulse_rotation.html", {
        "rotation": data.get("rotation", []),
    })


@router.get("/pulse-correlations", response_class=HTMLResponse)
async def partial_pulse_correlations(request: Request):
    data = pulse_source.get_cached() or {}
    return templates.TemplateResponse(request, "partials/pulse_correlations.html", {
        "correlations": data.get("correlations", {"labels": [], "matrix": []}),
    })


# ─── VIX Term Structure ───
@router.get("/pulse-vix-term", response_class=HTMLResponse)
async def partial_pulse_vix_term(request: Request):
    data = pulse_source.get_cached() or {}
    return templates.TemplateResponse(request, "partials/pulse_vix_term.html", {
        "vix_term": data.get("vix_term_structure", {"points": [], "shape": "unknown"}),
    })


# ─── Vol Event Countdown ───
@router.get("/vol-countdown", response_class=HTMLResponse)
async def partial_vol_countdown(request: Request):
    data = calendar_source.get_cached() or {"events": []}
    events = data.get("events", [])
    # Find next future high-impact event
    next_event = None
    for e in events:
        if not e.get("is_past") and e.get("impact") in ("High", "Holiday"):
            next_event = e
            break
    # Fallback to any future event
    if not next_event:
        for e in events:
            if not e.get("is_past"):
                next_event = e
                break
    return templates.TemplateResponse(request, "partials/vol_countdown.html", {
        "event": next_event,
    })


# ─── Mag 7 ───
@router.get("/mag7", response_class=HTMLResponse)
async def partial_mag7(request: Request):
    data = mag7_source.get_cached() or {"stocks": []}
    return templates.TemplateResponse(request, "partials/mag7.html", {
        "stocks": data.get("stocks", []),
    })


# ─── Commodities ───
@router.get("/commodities", response_class=HTMLResponse)
async def partial_commodities(request: Request, spark_period: str = "1W"):
    data = commodities_source.get_cached() or {"sectors": {}, "sector_meta": {}}
    return templates.TemplateResponse(request, "partials/commodities.html", {
        "sectors": data.get("sectors", {}),
        "sector_meta": data.get("sector_meta", {}),
        "spark_period": spark_period,
    })


# ─── Volatility Skew ───
@router.get("/vol-skew", response_class=HTMLResponse)
async def partial_vol_skew(request: Request):
    data = options_skew_source.get_cached() or {}
    return templates.TemplateResponse(request, "partials/vol_skew.html", {
        "skew": data,
    })


# ─── Earnings Calendar ───
@router.get("/earnings", response_class=HTMLResponse)
async def partial_earnings(request: Request):
    data = earnings_source.get_cached() or {"events": []}
    return templates.TemplateResponse(request, "partials/earnings.html", {
        "events": data.get("events", []),
    })


# ─── Fed Watch ───
@router.get("/fedwatch", response_class=HTMLResponse)
async def partial_fedwatch(request: Request):
    data = fedwatch_source.get_cached() or {}
    return templates.TemplateResponse(request, "partials/fedwatch.html", {
        "current_rates": data.get("current_rates", []),
        "upcoming_fomc": data.get("upcoming_fomc", []),
        "next_fomc": data.get("next_fomc"),
        "dot_plot_proxy": data.get("dot_plot_proxy"),
    })


# ─── COT Positioning ───
@router.get("/cot", response_class=HTMLResponse)
async def partial_cot(request: Request):
    data = cot_source.get_cached() or {"positions": []}
    positions = data.get("positions", [])
    # Group by category
    categories = {}
    for p in positions:
        cat = p.get("category", "Other")
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(p)
    return templates.TemplateResponse(request, "partials/cot.html", {
        "categories": categories,
        "report_date": positions[0].get("report_date") if positions else None,
    })



# ─── Commodity Research Panel ───
def _read_commodity_note(symbol: str) -> str | None:
    """Read the Obsidian research note for a commodity symbol."""
    meta = COMMODITY_LOOKUP.get(symbol)
    if not meta:
        return None
    fname = f"{symbol} \u2014 {meta['name']}.md"
    path = COMMODITY_NOTES_DIR / fname
    return path.read_text(encoding="utf-8") if path.exists() else None


def _parse_quick_ref(md: str | None, symbol: str) -> dict:
    """Extract structured data from raw Markdown for the side panel."""
    meta = COMMODITY_LOOKUP.get(symbol, {})
    result: dict = {"populated": bool(md), **meta}
    if not md:
        return result

    # Parse YAML frontmatter
    fm_match = re.match(r"^---\n(.*?)\n---", md, re.DOTALL)
    if fm_match:
        for line in fm_match.group(1).split("\n"):
            if ":" in line:
                k, _, v = line.partition(":")
                result[k.strip()] = v.strip()

    # Extract section content (first 8 non-blank lines per section)
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in md.split("\n"):
        if line.startswith("## "):
            current = line[3:].strip()
            sections[current] = []
        elif current and line.strip() and not line.startswith("#"):
            if len(sections[current]) < 8:
                sections[current].append(line)

    result["sections"] = sections
    return result


@router.get("/commodity-research", response_class=HTMLResponse)
async def partial_commodity_research(request: Request, symbol: str = Query(...)):
    note = _read_commodity_note(symbol)
    data = _parse_quick_ref(note, symbol)
    meta = COMMODITY_LOOKUP.get(symbol, {})
    name_enc = urllib.parse.quote(meta.get("name", ""), safe="")
    sym_enc = urllib.parse.quote(symbol, safe="")
    obsidian_uri = f"obsidian://open?vault=ZC_Mac_Vault&file=Commodities%2F{sym_enc}%20%E2%80%94%20{name_enc}"
    return templates.TemplateResponse(request, "partials/commodity_research.html", {
        "symbol": symbol,
        "data": data,
        "obsidian_uri": obsidian_uri,
    })


# ─── Source Health ───
def _fmt_age(secs: float | None) -> str:
    if secs is None:
        return "—"
    if secs < 60:
        return f"{int(secs)}s"
    elif secs < 3600:
        return f"{int(secs / 60)}m {int(secs % 60)}s"
    return f"{secs / 3600:.1f}h"


def _count_coverage(cache: dict | None) -> str:
    """Best-effort count of symbols with non-null prices in cache."""
    if not cache:
        return "—"
    total = non_null = 0
    for key, val in cache.items():
        if key.startswith("_"):
            continue
        if isinstance(val, list):
            for item in val:
                if isinstance(item, dict) and "price" in item:
                    total += 1
                    if item["price"] is not None:
                        non_null += 1
        elif isinstance(val, dict):
            for sub in val.values():
                if isinstance(sub, list):
                    for item in sub:
                        if isinstance(item, dict) and "price" in item:
                            total += 1
                            if item["price"] is not None:
                                non_null += 1
    if total == 0:
        return "ok" if cache else "—"
    return f"{non_null}/{total}"


@router.get("/source-health", response_class=HTMLResponse)
async def partial_source_health(request: Request):
    # Load reliability scores from telemetry
    try:
        from data_quality.scorer import score_all
        from data_quality.collector import event_count
        reliability = {s.source: s for s in score_all()}
        total_events = event_count()
    except Exception:
        reliability = {}
        total_events = 0

    rows = []
    for src in ALL_SOURCES:
        cache = src.get_cached()
        age = src.cache_age()

        if cache is None:
            status = "no-data"
        elif cache.get("error"):
            status = "error"
        elif age is None:
            status = "no-data"
        elif age < src.refresh_interval:
            status = "fresh"
        elif age < src.refresh_interval * 2:
            status = "stale"
        else:
            status = "very-stale"

        score = reliability.get(src.cache_key)
        rows.append({
            "name": src.cache_key,
            "interval_str": _fmt_age(src.refresh_interval),
            "age_str": _fmt_age(age),
            "age_secs": age,
            "status": status,
            "coverage": _count_coverage(cache),
            "error": cache.get("error") if cache else None,
            "reliability": score.composite if score else None,
            "p95_ms": score.p95_ms if score else None,
            "success_rate": score.success_rate if score else None,
        })

    # Sort: errors/no-data first, then by age descending
    status_order = {"error": 0, "no-data": 1, "very-stale": 2, "stale": 3, "fresh": 4}
    rows.sort(key=lambda r: (status_order.get(r["status"], 5), -(r["age_secs"] or 0)))

    return templates.TemplateResponse(request, "partials/source_health.html", {
        "rows": rows,
        "total_events": total_events,
    })


# ─── Shock Analogs ───
@router.get("/shocks", response_class=HTMLResponse)
async def partial_shocks(
    request: Request,
    shock_type: str = "supply",
    shock_subtype: str = "",
    severity: int = 3,
    cpi_elevated: str = "",
    economy_weakening: str = "",
    credit_spreads: str = "",
):
    data = shocks_source.get_cached() or {"shocks": []}
    shocks = data.get("shocks", [])

    if not shocks:
        return templates.TemplateResponse(request, "partials/shocks.html", {"error": "Shock database unavailable.", "analogs": []})

    matcher = ShockAnalogMatcher(shocks)
    analogs = matcher.find_analogs(
        shock_type=shock_type,
        shock_subtype=shock_subtype or None,
        severity=severity,
        cpi_elevated=(cpi_elevated == "true"),
        economy_weakening=(economy_weakening == "true"),
        credit_spreads_widening=(credit_spreads == "true"),
        top_n=3,
    )

    return templates.TemplateResponse(request, "partials/shocks.html", {
        "analogs": analogs,
        "shock_type": shock_type,
        "shock_subtype": shock_subtype,
        "severity": severity,
        "error": None,
    })


# ─── Signals ───
@router.get("/signals", response_class=HTMLResponse)
async def partial_signals(request: Request):
    from signals.run_eval import STRATEGY_REGISTRY
    from signals.htf_autoresearch import STRATEGY_REGISTRY as HTF_STRATEGY_REGISTRY
    from signals.htf_autoresearch import best_by_objective
    from signals.evaluate import _load_prices
    from signals import findings

    tactical_window_start = (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d")
    htf_window_start = (datetime.now() - timedelta(days=365 * 5)).strftime("%Y-%m-%d")
    leaderboard = findings.best_by_strategy()
    htf_leaderboard = best_by_objective()
    htf_strategy_names = set(HTF_STRATEGY_REGISTRY)
    signal_states = []
    registries = [
        ("Tactical", STRATEGY_REGISTRY),
        ("Higher timeframe", HTF_STRATEGY_REGISTRY),
    ]
    for lane, registry in registries:
        for name, StratClass in registry.items():
            best = htf_leaderboard.get(name) if name in htf_strategy_names else leaderboard.get(name)
            params = best.get("metadata", {}).get("params", {}) if best else {}
            strategy = StratClass(**params) if params else StratClass()
            needed = list(set(strategy.required_symbols() + [strategy.target_symbol]))
            start_date = htf_window_start if name in htf_strategy_names else tactical_window_start
            prices = _load_prices(needed, start=start_date)
            sigs = strategy.generate_signals(prices)
            last_val = int(sigs.iloc[-1]) if len(sigs) > 0 else 0
            last_date = str(sigs.index[-1].date()) if len(sigs) > 0 else "—"
            metadata = strategy.metadata()
            action_text = (
                metadata["trade_long"] if last_val == 1
                else metadata["trade_flat"] if last_val == 0
                else metadata["trade_short"]
            )
            signal_states.append({
                "name": name,
                "lane": lane,
                "signal": last_val,
                "label": "LONG" if last_val == 1 else "FLAT" if last_val == 0 else "SHORT",
                "date": last_date,
                "version": strategy.version,
                "target_symbol": strategy.target_symbol,
                "target_label": metadata["target_label"],
                "action_text": action_text,
                "cadence": metadata["cadence"],
                "sizing_note": metadata["sizing_note"],
                "params": strategy.params,
                "optimized": bool(best),
            })

    total_runs = findings.count()

    return templates.TemplateResponse(request, "partials/signals.html", {
        "signal_states": signal_states,
        "leaderboard": leaderboard,
        "htf_leaderboard": htf_leaderboard,
        "htf_strategy_names": htf_strategy_names,
        "total_runs": total_runs,
    })
