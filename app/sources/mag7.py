"""Mag 7 + AI heavyweight equities — price returns via Yahoo spark, fundamentals via yfinance."""

import asyncio

import yfinance as yf

from app.config import MAG7_STOCKS, REFRESH_MAG7
from app.sources.base import BaseSource, logger
from app.sources.yahoo_quotes import fetch_all_spark

# Trading-day offsets for return periods
RETURN_PERIODS = {
    "1M": 21,
    "6M": 126,
    "1Y": 252,
    "5Y": 1260,
    "10Y": 2500,
}


class Mag7Source(BaseSource):
    cache_key = "mag7"
    refresh_interval = REFRESH_MAG7

    async def fetch(self) -> dict:
        symbols = [s["symbol"] for s in MAG7_STOCKS]

        # Fast price + returns via spark API
        spark_data = await fetch_all_spark(symbols, time_range="10y")

        # Fundamentals still need yfinance Ticker.info (no fast alternative)
        fundamentals = await asyncio.to_thread(self._fetch_fundamentals, symbols)

        stocks = []
        for entry in MAG7_STOCKS:
            sym = entry["symbol"]
            sd = spark_data.get(sym)
            fund = fundamentals.get(sym, {})

            if sd and sd["closes"] and len(sd["closes"]) >= 2:
                price = sd["closes"][-1]
                prev = sd["closes"][-2]
                change_pct = round((price / prev - 1) * 100, 2) if prev else None
                returns = self._calc_returns_from_closes(sd["closes"])
            else:
                price = None
                change_pct = None
                returns = {}

            stocks.append({
                **entry,
                "price": round(price, 2) if price else None,
                "change_pct": change_pct,
                "ytd_pct": returns.get("ytd"),
                "returns": returns,
                "market_cap": fund.get("market_cap"),
                "pe_trailing": fund.get("pe_trailing"),
                "pe_forward": fund.get("pe_forward"),
                "eps_trailing": fund.get("eps_trailing"),
                "eps_forward": fund.get("eps_forward"),
                "pct_from_high": fund.get("pct_from_high", None),
                "rev_growth_yoy": fund.get("rev_growth_yoy"),
                "capex_yoy": fund.get("capex_yoy"),
            })

        return {"stocks": stocks}

    def _fetch_fundamentals(self, symbols: list[str]) -> dict:
        """Fetch fundamental data via yfinance Ticker.info (still needed for PE/EPS)."""
        results = {}
        for sym in symbols:
            try:
                t = yf.Ticker(sym)
                info = t.info or {}
                price = info.get("currentPrice") or info.get("regularMarketPrice")
                pe_t = info.get("trailingPE")
                pe_f = info.get("forwardPE")
                eps_t = info.get("trailingEps")
                eps_f = info.get("forwardEps")
                w52h = info.get("fiftyTwoWeekHigh")
                pct_from_high = None
                if price and w52h and w52h != 0:
                    pct_from_high = round((price / w52h - 1) * 100, 2)

                # Revenue growth YoY% and capex from financials
                rev_growth = None
                capex_yoy = None
                try:
                    inc = t.income_stmt
                    if inc is not None and not inc.empty and "Total Revenue" in inc.index and inc.shape[1] >= 2:
                        rev_curr = inc.loc["Total Revenue"].iloc[0]
                        rev_prev = inc.loc["Total Revenue"].iloc[1]
                        if rev_prev and rev_prev != 0:
                            rev_growth = round((rev_curr / rev_prev - 1) * 100, 1)

                    cf = t.cashflow
                    if cf is not None and not cf.empty and "Capital Expenditure" in cf.index and cf.shape[1] >= 2:
                        capex_curr = abs(cf.loc["Capital Expenditure"].iloc[0])
                        capex_prev = abs(cf.loc["Capital Expenditure"].iloc[1])
                        if capex_prev and capex_prev != 0:
                            capex_yoy = round((capex_curr / capex_prev - 1) * 100, 1)
                except Exception:
                    pass

                results[sym] = {
                    "market_cap": info.get("marketCap"),
                    "pe_trailing": round(pe_t, 2) if pe_t else None,
                    "pe_forward": round(pe_f, 2) if pe_f else None,
                    "eps_trailing": round(eps_t, 2) if eps_t else None,
                    "eps_forward": round(eps_f, 2) if eps_f else None,
                    "pct_from_high": pct_from_high,
                    "rev_growth_yoy": rev_growth,
                    "capex_yoy": capex_yoy,
                }
            except Exception as e:
                logger.debug("Mag7 fundamentals %s error: %s", sym, e)
                results[sym] = {}
        return results

    def _calc_returns_from_closes(self, closes: list[float]) -> dict:
        """Calculate multi-period returns + YTD from close prices."""
        if len(closes) < 2:
            return {}
        current = closes[-1]
        ret = {}

        # Period returns
        for label, days in RETURN_PERIODS.items():
            if len(closes) > days:
                past = closes[-(days + 1)]
                if past != 0:
                    ret[label] = round((current / past - 1) * 100, 2)

        return ret
