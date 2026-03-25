"""
backtester.py — Backtest de la stratégie momentum sur données historiques.

Logique :
- Rebalancement mensuel (premier jour de bourse de chaque mois)
- Top 1 : 50% / Top 2 : 50% parmi les ETFs passant le filtre MM200j
- Comparaison vs SPY sur la même période
- Résultats : NAV normalisée à 1, CAGR, max drawdown, alpha
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf
import yaml

logger = logging.getLogger(__name__)

_DAYS_1M = 21
_DAYS_3M = 63
_DAYS_MA200 = 200
_CASH_TICKER = "__CASH__"  # Pseudo-ticker quand aucun ETF éligible


class Backtester:
    def __init__(
        self,
        config_path: Path,
        settings: dict | None = None,
        tickers: list[dict] | None = None,
        eur_tickers: set[str] | None = None,
    ):
        config_path = Path(config_path)

        if settings is None:
            with open(config_path / "settings.yaml") as f:
                settings = yaml.safe_load(f)
        if tickers is None:
            with open(config_path / "tickers.yaml") as f:
                cfg = yaml.safe_load(f)
                tickers = cfg["universe"]
                eur_tickers = set(cfg.get("eur_tickers", []))

        self.universe: list[dict] = tickers
        self.eur_tickers: set[str] = eur_tickers or set()
        self.weight_1m: float = settings["momentum"]["weight_1m"]
        self.weight_3m: float = settings["momentum"]["weight_3m"]
        self.ma_days: int = settings["momentum"]["ma_filter_days"]

    # ──────────────────────────────────────────────────────────────────────────
    # API publique
    # ──────────────────────────────────────────────────────────────────────────

    def run(self, start_date: str, end_date: str | None = None) -> dict:
        """
        Lance le backtest entre start_date et end_date.

        Retourne un dict avec :
          - "portfolio"  : pd.DataFrame(index=date, columns=["nav"])
          - "spy"        : pd.DataFrame(index=date, columns=["nav"])
          - "stats"      : dict de métriques
          - "history"    : list de {date, holdings, score}
        """
        end_date = end_date or datetime.today().strftime("%Y-%m-%d")
        logger.info(f"Backtest {start_date} → {end_date}")

        # Fetch avec suffisamment d'historique pour les indicateurs
        fetch_start = (
            pd.Timestamp(start_date) - timedelta(days=_DAYS_MA200 + 50)
        ).strftime("%Y-%m-%d")

        data = self._fetch_all(fetch_start, end_date)

        # Dates de rebalancement : premier jour de bourse de chaque mois
        backtest_data = data.loc[start_date:]
        rebalance_dates = self._monthly_dates(backtest_data.index)

        # Simulation
        portfolio_nav = pd.Series(dtype=float)
        spy_nav = pd.Series(dtype=float)
        history = []

        port_value = 1.0
        spy_value = 1.0
        current_holdings: list[dict] = []
        prev_date = None

        for rb_date in rebalance_dates:
            # Mise à jour de la valeur entre deux rebalancements
            if prev_date is not None and current_holdings:
                period = data.loc[prev_date:rb_date]
                if len(period) > 1:
                    port_ret = self._period_return(period, current_holdings)
                    spy_ret = float(period["SPY"].iloc[-1] / period["SPY"].iloc[0] - 1)
                    port_value *= 1 + port_ret
                    spy_value *= 1 + spy_ret

            portfolio_nav[rb_date] = port_value
            spy_nav[rb_date] = spy_value

            # Nouveau scoring au rb_date
            hist = data.loc[:rb_date]
            holdings = self._score_and_select(hist)
            current_holdings = holdings
            history.append({"date": str(rb_date.date()), "holdings": holdings})

            prev_date = rb_date

        if portfolio_nav.empty:
            return {"error": "Aucune donnée disponible pour le backtest."}

        # Normalisation à 1 au départ
        port_df = portfolio_nav.to_frame("nav")
        spy_df = spy_nav.to_frame("nav")

        stats = self._compute_stats(port_df, spy_df)

        return {
            "portfolio": port_df,
            "spy": spy_df,
            "stats": stats,
            "history": history,
        }

    # ──────────────────────────────────────────────────────────────────────────
    # Méthodes internes
    # ──────────────────────────────────────────────────────────────────────────

    def _fetch_all(self, start: str, end: str) -> pd.DataFrame:
        all_tickers = [etf["ticker"] for etf in self.universe] + ["SPY", "EURUSD=X"]
        logger.info(f"Téléchargement backtest : {len(all_tickers)} tickers…")

        raw = yf.download(
            all_tickers, start=start, end=end,
            auto_adjust=True, progress=False, threads=True
        )
        data = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw

        # Conversion EUR→USD
        if "EURUSD=X" in data.columns:
            eurusd = data["EURUSD=X"].ffill()
            for ticker in self.eur_tickers:
                if ticker in data.columns:
                    data[ticker] = data[ticker] * eurusd

        return data.ffill()  # Forward-fill les jours fériés

    @staticmethod
    def _monthly_dates(index: pd.DatetimeIndex) -> list[pd.Timestamp]:
        """Premier jour de bourse de chaque mois présent dans l'index."""
        dates = []
        seen_months = set()
        for d in sorted(index):
            key = (d.year, d.month)
            if key not in seen_months:
                seen_months.add(key)
                dates.append(d)
        return dates

    def _score_and_select(self, hist: pd.DataFrame) -> list[dict]:
        """Retourne les holdings (max 2) éligibles triés par score."""
        eligible = []
        for etf in self.universe:
            ticker = etf["ticker"]
            if ticker not in hist.columns:
                continue
            series = hist[ticker].dropna()
            if len(series) < _DAYS_MA200 + 1:
                continue

            current = float(series.iloc[-1])
            ma200 = float(series.tail(_DAYS_MA200).mean())
            if current <= ma200:
                continue  # Filtre absolu

            if len(series) < _DAYS_1M + 1 or len(series) < _DAYS_3M + 1:
                continue

            ret_1m = float(series.iloc[-1] / series.iloc[-_DAYS_1M - 1] - 1)
            ret_3m = float(series.iloc[-1] / series.iloc[-_DAYS_3M - 1] - 1)
            score = self.weight_1m * ret_1m + self.weight_3m * ret_3m

            eligible.append({"ticker": ticker, "score": score, "ret_1m": ret_1m})

        eligible.sort(key=lambda x: (x["score"], x["ret_1m"]), reverse=True)
        top2 = eligible[:2]
        return [{"ticker": e["ticker"], "weight": 0.5} for e in top2]

    @staticmethod
    def _period_return(period: pd.DataFrame, holdings: list[dict]) -> float:
        """Rendement pondéré du portefeuille sur une période."""
        total = 0.0
        for h in holdings:
            ticker = h["ticker"]
            if ticker in period.columns:
                ret = float(period[ticker].iloc[-1] / period[ticker].iloc[0] - 1)
                total += h["weight"] * ret
        return total

    @staticmethod
    def _compute_stats(port_df: pd.DataFrame, spy_df: pd.DataFrame) -> dict:
        n_years = (port_df.index[-1] - port_df.index[0]).days / 365.25
        if n_years <= 0:
            return {}

        port_final = port_df["nav"].iloc[-1]
        spy_final = spy_df["nav"].iloc[-1]

        port_cagr = port_final ** (1 / n_years) - 1
        spy_cagr = spy_final ** (1 / n_years) - 1

        rolling_max = port_df["nav"].cummax()
        drawdowns = (port_df["nav"] - rolling_max) / rolling_max
        max_dd = float(drawdowns.min())

        return {
            "period": f"{port_df.index[0].date()} → {port_df.index[-1].date()}",
            "n_months": len(port_df),
            "portfolio_total_return": float(port_final - 1),
            "spy_total_return": float(spy_final - 1),
            "portfolio_cagr": float(port_cagr),
            "spy_cagr": float(spy_cagr),
            "alpha_annualized": float(port_cagr - spy_cagr),
            "max_drawdown": max_dd,
        }
