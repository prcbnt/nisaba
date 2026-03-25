"""
momentum_scorer.py — Calcul des scores de momentum et application du filtre absolu.

Formule : score = weight_3m × ret_3M_skip + weight_6m × ret_6M_skip
  - ret_3M_skip : rendement de J-63 à J-21 (63 jours, endpoint = il y a 1 mois)
  - ret_6M_skip : rendement de J-126 à J-21 (126 jours, endpoint = il y a 1 mois)

Le "skip" (skip_days = 21) exclut le mois le plus récent pour éviter l'effet
de reversal court terme documenté par Jegadeesh & Titman.

Filtre   : cours > MM200j  (standard Antonacci)
Tie-break : ret_3m si égalité de score
"""

import logging
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

logger = logging.getLogger(__name__)

# Constantes par défaut (surchargées par settings.yaml)
_DAYS_3M  = 63
_DAYS_6M  = 126
_SKIP     = 21


class MomentumScorer:
    def __init__(self, config_path: Path):
        config_path = Path(config_path)
        with open(config_path / "tickers.yaml") as f:
            ticker_cfg = yaml.safe_load(f)
        with open(config_path / "settings.yaml") as f:
            settings = yaml.safe_load(f)

        self.universe: list[dict] = ticker_cfg["universe"]
        self.weight_3m: float = settings["momentum"]["weight_3m"]
        self.weight_6m: float = settings["momentum"]["weight_6m"]
        self.skip_days: int   = settings["momentum"].get("skip_days", _SKIP)
        self.days_3m: int     = settings["momentum"].get("trading_days_3m", _DAYS_3M)
        self.days_6m: int     = settings["momentum"].get("trading_days_6m", _DAYS_6M)
        self.ma_days: int     = settings["momentum"]["ma_filter_days"]

    # ──────────────────────────────────────────────────────────────────────────
    # API publique
    # ──────────────────────────────────────────────────────────────────────────

    def compute_scores(self, prices: pd.DataFrame) -> pd.DataFrame:
        """
        Calcule les scores momentum pour tous les ETFs de l'univers.

        Retourne un DataFrame trié : éligibles (score desc) puis exclus.
        Colonnes : ticker, name, sector, region, ret_3m, ret_6m, score,
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

        # Historique minimum pour MM200 (contrainte la plus exigeante)
        if len(series) < self.ma_days + 1:
            logger.warning(
                f"{ticker} : historique trop court ({len(series)} j < {self.ma_days + 1})"
            )
            status = "données insuffisantes"
            return self._make_row(etf, series, np.nan, np.nan, np.nan, False, status)

        current = float(series.iloc[-1])

        # Rendements avec skip (endpoint = J-skip_days, pas J-0)
        ret_3m = self._return(series, self.days_3m, self.skip_days)
        ret_6m = self._return(series, self.days_6m, self.skip_days)

        # Filtre absolu MM200
        ma200 = float(series.tail(self.ma_days).mean())
        above_ma200 = current > ma200

        # Score composite
        if pd.notna(ret_3m) and pd.notna(ret_6m):
            score = self.weight_3m * ret_3m + self.weight_6m * ret_6m
        elif pd.notna(ret_3m):
            score = ret_3m  # fallback si historique insuffisant pour 6M
        else:
            score = np.nan

        if pd.isna(score):
            status = "données insuffisantes"
        elif not above_ma200:
            status = "exclu (sous MM200)"
        else:
            status = "✓"

        return self._make_row(etf, series, ret_3m, ret_6m, score, above_ma200, status, ma200, current)

    @staticmethod
    def _return(series: pd.Series, lookback_days: int, skip_days: int = 0) -> float:
        """
        Rendement sur lookback_days jours de bourse, endpoint à J-skip_days.

        Exemple : _return(series, 63, 21)
          → prix à J-21 / prix à J-84 - 1  (signal 3M-skip)
          → series.iloc[-(skip+1)] / series.iloc[-(lookback+skip+1)] - 1
        """
        total_needed = lookback_days + skip_days + 1
        if len(series) < total_needed:
            return np.nan
        end   = series.iloc[-(skip_days + 1)]
        start = series.iloc[-(lookback_days + skip_days + 1)]
        return float(end / start - 1)

    @staticmethod
    def _make_row(
        etf: dict,
        series: pd.Series,
        ret_3m,
        ret_6m,
        score,
        above_ma200: bool,
        status: str,
        ma200: float | None = None,
        current: float | None = None,
    ) -> dict:
        return {
            "ticker":        etf["ticker"],
            "name":          etf["name"],
            "sector":        etf["sector"],
            "region":        etf["region"],
            "current_price": current if current is not None else (float(series.iloc[-1]) if len(series) else np.nan),
            "ma200":         ma200,
            "above_ma200":   above_ma200,
            "ret_3m":        ret_3m,
            "ret_6m":        ret_6m,
            "score":         score,
            "status":        status,
        }

    @staticmethod
    def _rank(df: pd.DataFrame) -> pd.DataFrame:
        """
        Trie : éligibles par score desc (tie-break ret_3m), puis exclus par score desc.
        Assigne un rang uniquement aux éligibles.
        """
        eligible = (
            df[df["status"] == "✓"]
            .sort_values(by=["score", "ret_3m"], ascending=False)
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
