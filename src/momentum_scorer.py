"""
momentum_scorer.py — Calcul des scores de momentum, deux stratégies indépendantes.

Stratégie macro     : score = weight_3m × ret_3M_skip + weight_6m × ret_6M_skip
                      skip_days = 21 (évite le reversal court terme)
Stratégie thématique: score = weight_1m × ret_1M + weight_3m × ret_3M
                      skip_days = 0 (ETFs tendanciels, reversal moins marqué)

Instanciation :
    scorer_macro     = MomentumScorer(config_path, strategy="macro")
    scorer_thematic  = MomentumScorer(config_path, strategy="thematic")

Filtre   : cours > MM(ma_filter_days)j
Tie-break : ret_3m si égalité de score
"""

import logging
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

logger = logging.getLogger(__name__)

# Clé de l'univers dans tickers.yaml par stratégie
_UNIVERSE_KEY = {
    "macro":     "universe",
    "thematic":  "universe_thematic",
    "satellite": "universe_satellite",
}


class MomentumScorer:
    def __init__(self, config_path: Path, strategy: str = "macro"):
        config_path = Path(config_path)
        with open(config_path / "tickers.yaml") as f:
            ticker_cfg = yaml.safe_load(f)
        with open(config_path / "settings.yaml") as f:
            settings = yaml.safe_load(f)

        self.strategy = strategy
        universe_key = _UNIVERSE_KEY.get(strategy, "universe")
        self.universe: list[dict] = ticker_cfg[universe_key]

        # Lecture des paramètres depuis strategies[strategy] (avec fallback legacy)
        strat_cfg = settings.get("strategies", {}).get(strategy, settings.get("momentum", {}))

        self.weight_1m:  float = strat_cfg.get("weight_1m",  0.0)
        self.weight_3m:  float = strat_cfg.get("weight_3m",  0.5)
        self.weight_6m:  float = strat_cfg.get("weight_6m",  0.5)
        self.skip_days:  int   = strat_cfg.get("skip_days",  21)
        self.days_1m:    int   = strat_cfg.get("trading_days_1m", 21)
        self.days_3m:    int   = strat_cfg.get("trading_days_3m", 63)
        self.days_6m:    int   = strat_cfg.get("trading_days_6m", 126)
        self.ma_days:    int   = strat_cfg.get("ma_filter_days",  200)
        self.top_n_cfg:  int   = strat_cfg.get("top_n", 2)

    # ──────────────────────────────────────────────────────────────────────────
    # API publique
    # ──────────────────────────────────────────────────────────────────────────

    def compute_scores(self, prices: pd.DataFrame) -> pd.DataFrame:
        """
        Calcule les scores momentum pour tous les ETFs de l'univers courant.

        Retourne un DataFrame trié : éligibles (score desc) puis exclus.
        Colonnes : ticker, name, sector, region, ret_3m, ret_6m, score,
                   current_price, ma, above_ma, status, rank
        """
        rows = []
        for etf in self.universe:
            row = self._score_etf(etf, prices)
            if row:
                rows.append(row)

        if not rows:
            raise RuntimeError(
                f"Aucun ETF scoré pour la stratégie '{self.strategy}' — vérifier les données."
            )

        df = pd.DataFrame(rows)
        df = self._rank(df)
        return df

    def get_top_n(self, ranked: pd.DataFrame, n: int | None = None) -> list[dict]:
        """Retourne les N meilleurs ETFs éligibles (passant le filtre absolu)."""
        n = n or self.top_n_cfg
        eligible = ranked[ranked["status"] == "✓"].head(n)
        return eligible.to_dict("records")

    # ──────────────────────────────────────────────────────────────────────────
    # Méthodes internes
    # ──────────────────────────────────────────────────────────────────────────

    def _score_etf(self, etf: dict, prices: pd.DataFrame) -> dict | None:
        ticker = etf["ticker"]

        if ticker not in prices.columns:
            logger.warning(f"[{self.strategy}] {ticker} absent du DataFrame — ignoré")
            return None

        series = prices[ticker].dropna()

        min_required = max(self.ma_days, self.days_1m + self.skip_days + 1) if self.ma_days > 0 else self.days_1m + 2
        if len(series) < min_required:
            logger.warning(
                f"[{self.strategy}] {ticker} : historique trop court "
                f"({len(series)} j < {self.ma_days + 1})"
            )
            return self._make_row(etf, series, np.nan, np.nan, np.nan, np.nan, False,
                                  "données insuffisantes")

        current = float(series.iloc[-1])
        if self.ma_days > 0:
            ma = float(series.tail(self.ma_days).mean())
            above_ma = current > ma
        else:
            ma = None       # Filtre désactivé (satellite)
            above_ma = True

        ret_1m = self._return(series, self.days_1m, 0) if self.weight_1m > 0 else np.nan
        ret_3m = self._return(series, self.days_3m, self.skip_days)
        ret_6m = self._return(series, self.days_6m, self.skip_days) if self.weight_6m > 0 else np.nan

        # Score composite selon les poids de la stratégie
        score = 0.0
        if self.weight_1m > 0 and pd.notna(ret_1m):
            score += self.weight_1m * ret_1m
        if self.weight_3m > 0 and pd.notna(ret_3m):
            score += self.weight_3m * ret_3m
        if self.weight_6m > 0 and pd.notna(ret_6m):
            score += self.weight_6m * ret_6m

        if score == 0.0 and pd.isna(ret_3m):
            score = np.nan

        if pd.isna(score):
            status = "données insuffisantes"
        elif not above_ma:
            status = f"exclu (sous MM{self.ma_days})"
        else:
            status = "✓"

        return self._make_row(etf, series, ret_1m, ret_3m, ret_6m, score,
                              above_ma, status, ma if self.ma_days > 0 else None, current)

    @staticmethod
    def _return(series: pd.Series, lookback_days: int, skip_days: int = 0) -> float:
        """
        Rendement sur lookback_days jours, endpoint à J-skip_days.
        ex: _return(series, 63, 21) → price[J-21] / price[J-84] - 1
        """
        total_needed = lookback_days + skip_days + 1
        if len(series) < total_needed:
            return np.nan
        end   = series.iloc[-(skip_days + 1)] if skip_days > 0 else series.iloc[-1]
        start = series.iloc[-(lookback_days + skip_days + 1)]
        return float(end / start - 1)

    @staticmethod
    def _make_row(
        etf: dict,
        series: pd.Series,
        ret_1m, ret_3m, ret_6m, score,
        above_ma: bool,
        status: str,
        ma: float | None = None,
        current: float | None = None,
    ) -> dict:
        return {
            "ticker":        etf["ticker"],
            "name":          etf["name"],
            "sector":        etf["sector"],
            "region":        etf["region"],
            "current_price": current if current is not None else (float(series.iloc[-1]) if len(series) else np.nan),
            "ma":            ma,
            "above_ma":      above_ma,
            "ret_1m":        ret_1m,
            "ret_3m":        ret_3m,
            "ret_6m":        ret_6m,
            "score":         score,
            "status":        status,
        }

    @staticmethod
    def _rank(df: pd.DataFrame) -> pd.DataFrame:
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
        return pd.concat([eligible, excluded], ignore_index=True)
