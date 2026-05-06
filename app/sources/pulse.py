"""Macro Pulse — HUD indicators, commodity ratios, sector rotation, correlations."""

import numpy as np

from app.config import (
    REFRESH_INDICES, PULSE_INDICATORS, COMMODITY_RATIOS,
    ROTATION_SECTORS, VIX_TERM_STRUCTURE,
)
from app.sources.base import BaseSource, logger
from app.sources.yahoo_quotes import fetch_all_spark


class PulseSource(BaseSource):
    cache_key = "pulse"
    refresh_interval = REFRESH_INDICES

    async def fetch(self) -> dict:
        # Collect all symbols needed across all pulse sub-fetches
        all_symbols = set()
        all_symbols.update(i["symbol"] for i in PULSE_INDICATORS)
        for r in COMMODITY_RATIOS:
            all_symbols.add(r["numerator"])
            all_symbols.add(r["denominator"])
        all_symbols.add("SPY")
        all_symbols.update(s["symbol"] for s in ROTATION_SECTORS)
        all_symbols.update(v["symbol"] for v in VIX_TERM_STRUCTURE)
        # Correlation assets
        all_symbols.update(["^GSPC", "GC=F", "CL=F", "DX-Y.NYB", "HG=F", "^TNX", "BTC-USD", "^VIX"])

        # Single batch fetch for everything
        spark_data = await fetch_all_spark(list(all_symbols), time_range="10y")

        hud = self._parse_hud(spark_data)
        ratios = self._parse_ratios(spark_data)
        rotation = self._parse_rotation(spark_data)
        correlations = self._parse_correlations(spark_data)
        vix_term = self._parse_vix_term(spark_data)
        return {
            "hud": hud,
            "ratios": ratios,
            "rotation": rotation,
            "correlations": correlations,
            "vix_term_structure": vix_term,
        }

    def _parse_hud(self, spark_data: dict) -> list[dict]:
        """Top indicators with price + change from spark data."""
        results = []
        for entry in PULSE_INDICATORS:
            sym = entry["symbol"]
            sd = spark_data.get(sym)
            if sd and sd["closes"] and len(sd["closes"]) >= 2:
                price = sd["closes"][-1]
                prev = sd["closes"][-2]
                chg = price - prev
                pct = (chg / prev * 100) if prev else 0
                results.append({
                    **entry,
                    "price": round(price, 2),
                    "change": round(chg, 2),
                    "change_pct": round(pct, 2),
                })
            else:
                results.append({**entry, "price": None, "change": None, "change_pct": None})
        return results

    def _parse_ratios(self, spark_data: dict) -> list[dict]:
        """Commodity proxy ratios from spark data."""
        results = []
        for ratio in COMMODITY_RATIOS:
            num_sd = spark_data.get(ratio["numerator"])
            den_sd = spark_data.get(ratio["denominator"])
            if (num_sd and den_sd and num_sd["closes"] and den_sd["closes"]
                    and len(num_sd["closes"]) >= 2 and len(den_sd["closes"]) >= 2):
                num_price = num_sd["closes"][-1]
                den_price = den_sd["closes"][-1]
                if den_price and den_price != 0:
                    current = num_price / den_price
                    prev_ratio = num_sd["closes"][-2] / den_sd["closes"][-2]
                    chg = ((current / prev_ratio) - 1) * 100 if prev_ratio else None
                    results.append({
                        **ratio,
                        "value": round(current, 2),
                        "change_pct": round(chg, 2) if chg is not None else None,
                    })
                else:
                    results.append({**ratio, "value": None, "change_pct": None})
            else:
                results.append({**ratio, "value": None, "change_pct": None})
        return results

    def _parse_rotation(self, spark_data: dict) -> list[dict]:
        """Sector relative strength vs SPY over 1M and 3M."""
        spy_sd = spark_data.get("SPY")
        if not spy_sd or not spy_sd["closes"] or len(spy_sd["closes"]) < 22:
            return []

        spy = spy_sd["closes"]
        spy_1m = (spy[-1] / spy[-22] - 1) * 100
        spy_3m = (spy[-1] / spy[-min(63, len(spy) - 1)] - 1) * 100

        results = []
        for sector in ROTATION_SECTORS:
            sym = sector["symbol"]
            sd = spark_data.get(sym)
            if not sd or not sd["closes"] or len(sd["closes"]) < 22:
                results.append({**sector, "rs_1m": None, "rs_3m": None, "abs_1m": None})
                continue

            s = sd["closes"]
            abs_1m = (s[-1] / s[-22] - 1) * 100
            abs_3m = (s[-1] / s[-min(63, len(s) - 1)] - 1) * 100
            rs_1m = abs_1m - spy_1m
            rs_3m = abs_3m - spy_3m

            results.append({
                **sector,
                "abs_1m": round(abs_1m, 2),
                "rs_1m": round(rs_1m, 2),
                "rs_3m": round(rs_3m, 2),
            })
        return results

    def _parse_vix_term(self, spark_data: dict) -> dict:
        """VIX term structure from spark data."""
        points = []
        for entry in VIX_TERM_STRUCTURE:
            sym = entry["symbol"]
            sd = spark_data.get(sym)
            if sd and sd["closes"]:
                price = sd["closes"][-1]
                points.append({
                    "label": entry["name"],
                    "tenor_days": entry["tenor_days"],
                    "value": round(price, 2),
                })
            else:
                points.append({"label": entry["name"], "tenor_days": entry["tenor_days"], "value": None})

        spot = next((p["value"] for p in points if p["tenor_days"] == 0), None)
        three_m = next((p["value"] for p in points if p["tenor_days"] == 90), None)
        if spot is not None and three_m is not None:
            shape = "contango" if spot < three_m else "backwardation"
        else:
            shape = "unknown"

        return {"points": points, "shape": shape}

    def _parse_correlations(self, spark_data: dict) -> dict:
        """Rolling 30-day correlation matrix from spark data."""
        corr_symbols = {
            "S&P 500": "^GSPC",
            "Gold": "GC=F",
            "Oil": "CL=F",
            "DXY": "DX-Y.NYB",
            "Copper": "HG=F",
            "10Y Yield": "^TNX",
            "Bitcoin": "BTC-USD",
            "VIX": "^VIX",
        }

        try:
            labels = list(corr_symbols.keys())
            sym_list = list(corr_symbols.values())

            # Build daily returns from spark close data (last 31 days → 30 returns)
            returns_by_sym = {}
            for sym in sym_list:
                sd = spark_data.get(sym)
                if sd and sd["closes"] and len(sd["closes"]) > 31:
                    closes = sd["closes"][-31:]
                    rets = [(closes[i] / closes[i - 1] - 1) for i in range(1, len(closes))]
                    returns_by_sym[sym] = rets

            matrix = []
            for i, s1 in enumerate(sym_list):
                row = []
                for j, s2 in enumerate(sym_list):
                    if s1 not in returns_by_sym or s2 not in returns_by_sym:
                        row.append(None)
                    elif i == j:
                        row.append(1.0)
                    else:
                        r1 = np.array(returns_by_sym[s1])
                        r2 = np.array(returns_by_sym[s2])
                        min_len = min(len(r1), len(r2))
                        if min_len < 5:
                            row.append(None)
                        else:
                            corr = float(np.corrcoef(r1[:min_len], r2[:min_len])[0, 1])
                            row.append(round(corr, 2) if not np.isnan(corr) else None)
                matrix.append(row)

            # Hierarchical clustering to reorder for visual grouping
            try:
                from scipy.cluster.hierarchy import linkage, leaves_list
                from scipy.spatial.distance import squareform

                n = len(labels)
                dist = np.zeros((n, n))
                for i in range(n):
                    for j in range(n):
                        v = matrix[i][j]
                        dist[i][j] = 1.0 - abs(v) if v is not None else 1.0

                condensed = squareform(dist, checks=False)
                Z = linkage(condensed, method="average")
                order = list(leaves_list(Z))

                labels = [labels[i] for i in order]
                matrix = [[matrix[i][j] for j in order] for i in order]
            except Exception as e:
                logger.debug("Clustering fallback (scipy): %s", e)

            return {"labels": labels, "matrix": matrix}
        except Exception as e:
            logger.debug("Correlation error: %s", e)
            return {"labels": [], "matrix": []}
