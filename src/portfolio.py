"""
portfolio.py — Gestion de l'état du portefeuille (deux stratégies indépendantes).

Structure du fichier JSON :
  {
    "macro":    { "current_allocation": [...], "last_rebalance_date": "...", "history": [...] },
    "thematic": { "current_allocation": [...], "last_rebalance_date": null,  "history": [...] }
  }

Migration automatique : si l'ancien format (current_allocation à la racine) est détecté,
il est migré vers la clé "macro".
"""

import json
import logging
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

_TRADING_DAYS_1W = 5
_STRATEGIES = ("macro", "thematic")


class PortfolioManager:
    def __init__(self, state_path: Path, strategy: str = "macro"):
        if strategy not in _STRATEGIES:
            raise ValueError(f"Stratégie inconnue : {strategy!r} — choisir parmi {_STRATEGIES}")
        self.state_path = Path(state_path)
        self.strategy = strategy
        self._full_state = self._load()

    @property
    def _state(self) -> dict:
        return self._full_state[self.strategy]

    def get_current_allocation(self) -> list[dict]:
        return self._state.get("current_allocation", [])

    def is_empty(self) -> bool:
        return len(self.get_current_allocation()) == 0

    def update_allocation(self, top_n: list[dict]) -> None:
        old = self.get_current_allocation()
        new = [
            {
                "ticker":         etf["ticker"],
                "name":           etf["name"],
                "weight":         0.5,
                "score_at_entry": round(float(etf["score"]), 6) if pd.notna(etf["score"]) else None,
                "entry_date":     str(date.today()),
            }
            for etf in top_n[:2]
        ]
        self._state["history"].append({"date": str(date.today()), "from": old, "to": new})
        self._state["current_allocation"] = new
        self._state["last_rebalance_date"] = str(date.today())
        self._save()
        logger.info(
            f"[{self.strategy}] Allocation mise à jour : "
            f"{[e['ticker'] for e in new]} "
            f"(était : {[e['ticker'] for e in old] or 'vide'})"
        )

    def needs_rebalancing(self, top_n: list[dict]) -> bool:
        current_tickers = {h["ticker"] for h in self.get_current_allocation()}
        new_tickers     = {e["ticker"] for e in top_n[:2]}
        return current_tickers != new_tickers

    def compute_weekly_performance(self, prices: pd.DataFrame) -> dict:
        allocation = self.get_current_allocation()
        if not allocation:
            return {}
        results = {}
        for holding in allocation:
            ticker = holding["ticker"]
            if ticker not in prices.columns:
                results[ticker] = {"name": holding["name"], "weight": holding["weight"], "ret_1w": None}
                continue
            series = prices[ticker].dropna()
            ret_1w = (
                float(series.iloc[-1] / series.iloc[-_TRADING_DAYS_1W - 1] - 1)
                if len(series) >= _TRADING_DAYS_1W + 1 else None
            )
            results[ticker] = {"name": holding["name"], "weight": holding["weight"], "ret_1w": ret_1w}
        return results

    def _load(self) -> dict:
        if not self.state_path.exists():
            logger.warning(f"Fichier d'état introuvable : {self.state_path} — initialisation")
            return self._empty_full_state()
        with open(self.state_path) as f:
            data = json.load(f)
        # Migration ancien format
        if "current_allocation" in data and "macro" not in data:
            logger.info("Migration portfolio_state.json vers format dual-stratégie")
            migrated = self._empty_full_state()
            migrated["macro"]["current_allocation"] = data.get("current_allocation", [])
            migrated["macro"]["last_rebalance_date"] = data.get("last_rebalance_date")
            migrated["macro"]["history"] = data.get("history", [])
            self._full_state = migrated
            self._save()
            return migrated
        for strat in _STRATEGIES:
            if strat not in data:
                data[strat] = self._empty_strategy_state()
        return data

    def _save(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_path, "w") as f:
            json.dump(self._full_state, f, indent=2, default=str, ensure_ascii=False)

    @staticmethod
    def _empty_strategy_state() -> dict:
        return {"current_allocation": [], "last_rebalance_date": None, "history": []}

    @classmethod
    def _empty_full_state(cls) -> dict:
        return {strat: cls._empty_strategy_state() for strat in _STRATEGIES}
