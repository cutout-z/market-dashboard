"""Mag 7 + AI heavyweight equities — price returns via Yahoo spark, fundamentals via yfinance."""

import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import yfinance as yf

from app.config import MAG7_STOCKS, REFRESH_MAG7
from app.sources.base import BaseSource, logger
from app.sources.yahoo_quotes import fetch_all_spark

# Trading-day offsets for return periods
RETURN_PERIODS = {
    "1M": 21,
    "3M": 63,
    "6M": 126,
    "1Y": 252,
    "5Y": 1260,
    "10Y": 2500,
}

MAG7_TICKERS = {"AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA"}
_SP500_DIVISOR = 8.9e9


class Mag7Source(BaseSource):
    cache_key = "mag7"
    refresh_interval = REFRESH_MAG7

    async def fetch(self) -> dict:
        symbols = [s["symbol"] for s in MAG7_STOCKS]

        # Fast price + returns via spark API
        spark_data = await fetch_all_spark(symbols + ["^GSPC"], time_range="10y")

        # Fundamentals still need yfinance Ticker.info (no fast alternative)
        fundamentals, valuation_heat, chat_etf = await asyncio.to_thread(
            self._fetch_fundamentals_and_heat, symbols, spark_data
        )

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
                "returns": returns,
                "market_cap": fund.get("market_cap"),
                "pe_trailing": fund.get("pe_trailing"),
                "pe_forward": fund.get("pe_forward"),
                "eps_trailing": fund.get("eps_trailing"),
                "eps_forward": fund.get("eps_forward"),
                "week52_low": fund.get("week52_low"),
                "week52_high": fund.get("week52_high"),
                "target_mean_1y": fund.get("target_mean_1y"),
                "pct_from_high": fund.get("pct_from_high"),
                "rev_growth_yoy": fund.get("rev_growth_yoy"),
                "capex_yoy": fund.get("capex_yoy"),
            })

        valuation_heat.update(self._mag7_concentration(stocks, spark_data))
        return {"stocks": stocks, "valuation_heat": valuation_heat, "chat_etf": chat_etf}

    def _has_real_data(self, data: dict) -> bool:
        stocks = data.get("stocks", [])
        return any(
            s.get("price") is not None or s.get("market_cap") is not None
            for s in stocks
            if isinstance(s, dict)
        )

    def _fetch_fundamentals_and_heat(self, symbols: list[str], spark_data: dict) -> tuple[dict, dict, dict]:
        fundamentals = self._fetch_fundamentals(symbols)
        valuation_heat = self._fetch_valuation_heat()
        chat_etf = self._fetch_chat_etf()
        return fundamentals, valuation_heat, chat_etf

    def _fetch_fundamentals(self, symbols: list[str]) -> dict:
        """Fetch fundamental data via yfinance, parallelised to keep refreshes tolerable."""
        results = {}
        with ThreadPoolExecutor(max_workers=6) as pool:
            futures = {pool.submit(self._fetch_one_fundamental, sym): sym for sym in symbols}
            for future in as_completed(futures):
                sym, data = future.result()
                results[sym] = data
        return results

    def _fetch_one_fundamental(self, sym: str) -> tuple[str, dict]:
        try:
            t = yf.Ticker(sym)

            fast_info = None
            try:
                fast_info = t.fast_info
            except Exception:
                pass

            info = {}
            try:
                info = t.info or {}
            except Exception:
                pass

            price = _fast_attr(fast_info, "last_price") or info.get("currentPrice") or info.get("regularMarketPrice")
            market_cap = _fast_attr(fast_info, "market_cap") or info.get("marketCap")
            w52h = _fast_attr(fast_info, "year_high") or info.get("fiftyTwoWeekHigh")
            w52l = _fast_attr(fast_info, "year_low") or info.get("fiftyTwoWeekLow")
            pe_t = info.get("trailingPE")
            pe_f = info.get("forwardPE")
            eps_t = info.get("trailingEps")
            eps_f = info.get("forwardEps")
            target_1y = info.get("targetMeanPrice")

            if target_1y is None:
                try:
                    targets = t.analyst_price_targets or {}
                    target_1y = targets.get("mean") or targets.get("median")
                except Exception:
                    pass

            pct_from_high = None
            if price and w52h and w52h != 0:
                pct_from_high = round((price / w52h - 1) * 100, 2)

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

            return sym, {
                "market_cap": market_cap,
                "pe_trailing": round(pe_t, 2) if pe_t else None,
                "pe_forward": round(pe_f, 2) if pe_f else None,
                "eps_trailing": round(eps_t, 2) if eps_t else None,
                "eps_forward": round(eps_f, 2) if eps_f else None,
                "week52_low": round(w52l, 2) if w52l else None,
                "week52_high": round(w52h, 2) if w52h else None,
                "target_mean_1y": round(target_1y, 2) if target_1y else None,
                "pct_from_high": pct_from_high,
                "rev_growth_yoy": rev_growth,
                "capex_yoy": capex_yoy,
            }
        except Exception as e:
            logger.debug("Mag7 fundamentals %s error: %s", sym, e)
            return sym, {}

    def _fetch_valuation_heat(self) -> dict:
        heat = {"qqq_pe": None}
        try:
            qqq_info = yf.Ticker("QQQ").info or {}
            qqq_pe = qqq_info.get("trailingPE")
            if qqq_pe:
                heat["qqq_pe"] = round(qqq_pe, 1)
        except Exception as e:
            logger.debug("QQQ valuation heat error: %s", e)
        return heat

    def _mag7_concentration(self, stocks: list[dict], spark_data: dict) -> dict:
        mag7_stocks = [s for s in stocks if s["symbol"] in MAG7_TICKERS and s.get("market_cap")]
        if not mag7_stocks:
            return {"mag7_total_market_cap": None, "sp500_market_cap_est": None, "mag7_sp500_pct": None}

        mag7_total = sum(s["market_cap"] for s in mag7_stocks)
        gspc = spark_data.get("^GSPC", {})
        sp500_market_cap_est = None
        mag7_sp500_pct = None
        if gspc.get("closes"):
            sp500_market_cap_est = gspc["closes"][-1] * _SP500_DIVISOR
            if sp500_market_cap_est:
                mag7_sp500_pct = round(mag7_total / sp500_market_cap_est * 100, 1)

        return {
            "mag7_total_market_cap": mag7_total,
            "sp500_market_cap_est": sp500_market_cap_est,
            "mag7_sp500_pct": mag7_sp500_pct,
            "dotcom_top5_pct": 18,
        }

    def _fetch_chat_etf(self) -> dict:
        chat = {"holdings": []}
        try:
            ticker = yf.Ticker("CHAT")
            info = ticker.info or {}
            price = info.get("regularMarketPrice") or info.get("currentPrice") or info.get("previousClose")
            chat.update({
                "price": round(price, 2) if price else None,
                "aum": info.get("totalAssets"),
                "ytd_return": round(info.get("ytdReturn") * 100, 1) if info.get("ytdReturn") is not None else None,
                "week52_low": info.get("fiftyTwoWeekLow"),
                "week52_high": info.get("fiftyTwoWeekHigh"),
            })

            holdings = self._fetch_chat_holdings()
            if holdings:
                pe_map = self._fetch_holding_pes([h["symbol"] for h in holdings])
                covered = []
                for holding in holdings:
                    pe = pe_map.get(holding["symbol"], {})
                    holding["forward_pe"] = pe.get("forward_pe")
                    holding["trailing_pe"] = pe.get("trailing_pe")
                    if holding["forward_pe"] is not None:
                        covered.append((holding["weight_raw"], holding["forward_pe"]))
                if covered:
                    covered_weight = sum(weight for weight, _ in covered)
                    if covered_weight:
                        chat["weighted_forward_pe"] = round(
                            sum(weight * pe for weight, pe in covered) / covered_weight, 1
                        )
                chat["holdings"] = holdings
        except Exception as e:
            logger.debug("CHAT ETF fetch error: %s", e)
        return chat

    def _fetch_chat_holdings(self) -> list[dict]:
        try:
            resp = requests.get(
                "https://query2.finance.yahoo.com/v10/finance/quoteSummary/CHAT",
                params={"modules": "topHoldings"},
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=10,
            )
            raw = []
            if resp.status_code == 200:
                raw = (resp.json().get("quoteSummary", {})
                              .get("result", [{}])[0]
                              .get("topHoldings", {})
                              .get("holdings", []))
            if raw:
                holdings = []
                for h in raw[:12]:
                    weight = h.get("holdingPercent", {}).get("raw") or 0
                    holdings.append({
                        "symbol": h.get("symbol") or "",
                        "name": h.get("holdingName") or "",
                        "weight_raw": weight,
                        "weight_pct": round(weight * 100, 1),
                    })
                return [h for h in holdings if h["symbol"]]

            funds_data = yf.Ticker("CHAT").get_funds_data()
            top_holdings = getattr(funds_data, "top_holdings", None)
            if top_holdings is None or top_holdings.empty:
                return []

            holdings = []
            df = top_holdings.reset_index().head(12)
            for _, row in df.iterrows():
                weight = row.get("Holding Percent") or 0
                holdings.append({
                    "symbol": row.get("Symbol") or "",
                    "name": row.get("Name") or "",
                    "weight_raw": float(weight),
                    "weight_pct": round(float(weight) * 100, 1),
                })
            return [h for h in holdings if h["symbol"]]
        except Exception as e:
            logger.debug("CHAT holdings fetch error: %s", e)
            return []

    def _fetch_holding_pes(self, symbols: list[str]) -> dict:
        results = {}
        with ThreadPoolExecutor(max_workers=6) as pool:
            futures = {pool.submit(self._fetch_holding_pe, sym): sym for sym in symbols}
            for future in as_completed(futures):
                sym, data = future.result()
                results[sym] = data
        return results

    def _fetch_holding_pe(self, sym: str) -> tuple[str, dict]:
        try:
            info = yf.Ticker(sym).info or {}
            fpe = info.get("forwardPE")
            tpe = info.get("trailingPE")
            return sym, {
                "forward_pe": round(fpe, 1) if fpe and 0 < fpe < 5000 else None,
                "trailing_pe": round(tpe, 1) if tpe and 0 < tpe < 5000 else None,
            }
        except Exception:
            return sym, {"forward_pe": None, "trailing_pe": None}

    def _calc_returns_from_closes(self, closes: list[float]) -> dict:
        """Calculate multi-period returns from close prices."""
        if len(closes) < 2:
            return {}
        current = closes[-1]
        ret = {}

        for label, days in RETURN_PERIODS.items():
            if len(closes) > days:
                past = closes[-(days + 1)]
                if past != 0:
                    ret[label] = round((current / past - 1) * 100, 2)

        return ret


def _fast_attr(obj, name: str):
    if obj is None:
        return None
    try:
        return getattr(obj, name, None)
    except Exception:
        return None
