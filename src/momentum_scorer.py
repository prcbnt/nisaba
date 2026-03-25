"""
momentum_scorer.py — Calcul des scores de momentum et application du filtre absolu.

Formule : score = weight_1m × rendement_1M + weight_3m × rendement_3M
Filtre   : cours > MM200j  (standard Antonacci)
Tie-break : rendement_1M si égalité de score
"""

import logging
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

logger = logging.getLogger(__name__)

# Nombre de jours de bourse par fenêtre temporelle
_DAYS_1M = 21
_DAYS_3M = 63


class MomentumScorer:
    def __init__(self, config_path: Path):
        config_path = Path(config_path)
        with open(config_path / "tickers.yaml") as f:
            ticker_cfg = yaml.safe_load(f)
        with open(config_path / "settings.yaml") as f:
            settings = yaml.safe_load(f)

        self.universe: list[dict] = ticker_cfg["universe"]
        self.weight_1m: float = settings["momentum"]["weight_1m"]
        self.weight_3m: float = settings["momentum"]["weight_3m"]
        self.ma_days: int = settings["momentum"]["ma_filter_days"]

    # ──────────────────────────────────────────────────────────────────────────
    # API publique
    # ──────────────────────────────────────────────────────────────────────────

    def compute_scores(self, prices: pd.DataFrame) -> pd.DataFrame:
        """
        Calcule les scores momentum pour tous les ETFs de l'univers.

        Retourne un DataFrame trié : éligibles (score desc) puis exclus.
        Colonnes : ticker, name, sector, region, ret_1m, ret_3m, score,
                   current_price, ma200, above_ma200, status, rank
        """
        rows = []
        for etf in self.universe:
            row = self._score_etf(etf, prices)
            if row:
                rows.append(row)

        if not rows:
            raise RuntimeError("Aucun ETF scoré — vérifier les données de cours.")

        df = pd.DataFrame(rows)
        df = self._rank(df)
        return df

    def get_top_n(self, ranked: pd.DataFrame, n: int = 2) -> list[dict]:
        """Retourne les N meilleurs ETFs éligibles (passant le filtre absolu)."""
        eligible = ranked[ranked["status"] == "✓"].head(n)
        return eligible.to_dict("records")

    # ──────────────────────────────────────────────────────────────────────────
    # Méthodes internes
    # ──────────────────────────────────────────────────────────────────────────

    def _score_etf(self, etf: dict, prices: pd.DataFrame) -> dict | None:
        ticker = etf["ticker"]

        if ticker not in prices.columns:
            logger.warning(f"{ticker} absent du DataFrame de prix — ignoré")
            return None

        series = prices[ticker].dropna()

        # Historique insuffisant pour MM200
        if len(series) < self.ma_days + 1:
            logger.warning(
                f"{ticker} : historique trop court ({len(series)} j < {self.ma_days + 1})"
            )
            status = "données insuffisantes"
            return self._make_row(etf, series, np.nan, np.nan, np.nan, False, status)

        current = float(series.iloc[-1])

        # Rendements
        ret_1m = self._return(series, _DAYS_1M)
        ret_3m = self._return(series, _DAYS_3M)

        # Filtre absolu MM200
        ma200 = float(series.tail(self.ma_days).mean())
        above_ma200 = current > ma200

        # Score composite
        if pd.notna(ret_1m) and pd.notna(ret_3m):
            score = self.weight_1m * ret_1m + self.weight_3m * ret_3m
        else:
            score = np.nan

        if pd.isna(score):
            status = "données insuffisantes"
        elif not above_ma200:
            status = "exclu (sous MM200)"
        else:
            status = "✓"

        return self._make_row(etf, series, ret_1m, ret_3m, score, above_ma200, status, ma200, current)

    @staticmethod
    def _return(series: pd.Series, trading_days: int) -> float | None:
        """Rendement simple sur N jours de bourse."""
        if len(series) < trading_days + 1:
            return np.nan
        return float(series.iloc[-1] / series.iloc[-trading_days - 1] - 1)

    @staticmethod
    def _make_row(
        etf: dict,
        series: pd.Series,
        ret_1m,
        ret_3m,
        score,
        above_ma200: bool,
        status: str,
        ma200: float | None = None,
        current: float | None = None,
    ) -> dict:
        return {
            "ticker": etf["ticker"],
            "name": etf["name"],
            "sector": etf["sector"],
            "region": etf["region"],
            "current_price": current if current is not None else (float(series.iloc[-1]) if len(series) else np.nan),
            "ma200": ma200,
            "above_ma200": above_ma200,
            "ret_1m": ret_1m,
            "ret_3m": ret_3m,
            "score": score,
            "status": status,
        }

    @staticmethod
    def _rank(df: pd.DataFrame) -> pd.DataFrame:
        """
        Trie : éligibles par score desc (tie-break ret_1m), puis exclus par score desc.
        Assigne un rang uniquement aux éligibles.
        """
        eligible = (
            df[df["status"] == "✓"]
            .sort_values(by=["score", "ret_1m"], ascending=False)
            .reset_index(drop=True)
        )
        excluded = (
            df[df["status"] != "✓"]
            .sort_values(by=["score"], ascending=False, na_position="last")
            .reset_index(drop=True)
        )

        eligible["rank"] = range(1, len(eligible) + 1)
        excluded["rank"] = np.nan

        ranked = pd.concat([eligible, excluded], ignore_index=True)
        return ranked
