"""
portfolio.py — Gestion de l'état du portefeuille et calcul des performances.

L'état est persisté dans data/portfolio_state.json et mis à jour à chaque
rebalancement mensuel. Ce fichier est commité automatiquement par GitHub Actions.
"""

import json
import logging
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

_TRADING_DAYS_1W = 5


class PortfolioManager:
    def __init__(self, state_path: Path):
        self.state_path = Path(state_path)
        self.state = self._load()

    # ──────────────────────────────────────────────────────────────────────────
    # Lecture de l'état
    # ──────────────────────────────────────────────────────────────────────────

    def get_current_allocation(self) -> list[dict]:
        """Retourne les positions actuelles [{ticker, name, weight, entry_date, …}]."""
        return self.state.get("current_allocation", [])

    def is_empty(self) -> bool:
        return len(self.get_current_allocation()) == 0

    # ──────────────────────────────────────────────────────────────────────────
    # Mise à jour après rebalancement
    # ──────────────────────────────────────────────────────────────────────────

    def update_allocation(self, top_n: list[dict]) -> None:
        """Remplace l'allocation courante par les nouveaux Top N et sauvegarde."""
        old = self.get_current_allocation()
        new = [
            {
                "ticker": etf["ticker"],
                "name": etf["name"],
                "weight": 0.5,
                "score_at_entry": round(float(etf["score"]), 6) if pd.notna(etf["score"]) else None,
                "entry_date": str(date.today()),
            }
            for etf in top_n[:2]
        ]

        self.state["history"].append(
            {
                "date": str(date.today()),
                "from": old,
                "to": new,
            }
        )
        self.state["current_allocation"] = new
        self.state["last_rebalance_date"] = str(date.today())
        self._save()

        logger.info(
            f"Allocation mise à jour : {[e['ticker'] for e in new]} "
            f"(était : {[e['ticker'] for e in old] or 'vide'})"
        )

    def needs_rebalancing(self, top_n: list[dict]) -> bool:
        """True si le nouveau Top 2 diffère de l'allocation actuelle."""
        current_tickers = {h["ticker"] for h in self.get_current_allocation()}
        new_tickers = {e["ticker"] for e in top_n[:2]}
        return current_tickers != new_tickers

    # ──────────────────────────────────────────────────────────────────────────
    # Performance hebdomadaire
    # ──────────────────────────────────────────────────────────────────────────

    def compute_weekly_performance(self, prices: pd.DataFrame) -> dict:
        """
        Calcule la performance sur les 5 derniers jours de bourse
        pour chaque ETF en portefeuille.

        Retourne : {ticker: {name, weight, ret_1w}}
        """
        allocation = self.get_current_allocation()
        if not allocation:
            return {}

        results = {}
        for holding in allocation:
            ticker = holding["ticker"]
            if ticker not in prices.columns:
                logger.warning(f"{ticker} absent des prix — performance non calculable")
                results[ticker] = {"name": holding["name"], "weight": holding["weight"], "ret_1w": None}
                continue

            series = prices[ticker].dropna()
            if len(series) >= _TRADING_DAYS_1W + 1:
                ret_1w = float(series.iloc[-1] / series.iloc[-_TRADING_DAYS_1W - 1] - 1)
            else:
                ret_1w = None

            results[ticker] = {
                "name": holding["name"],
                "weight": holding["weight"],
                "ret_1w": ret_1w,
            }

        return results

    # ──────────────────────────────────────────────────────────────────────────
    # Persistance
    # ──────────────────────────────────────────────────────────────────────────

    def _load(self) -> dict:
        if self.state_path.exists():
            with open(self.state_path) as f:
                return json.load(f)
        logger.warning(f"Fichier d'état introuvable : {self.state_path} — état vide initialisé")
        return {"current_allocation": [], "last_rebalance_date": None, "history": []}

    def _save(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_path, "w") as f:
            json.dump(self.state, f, indent=2, default=str, ensure_ascii=False)
        logger.info(f"État sauvegardé → {self.state_path}")
