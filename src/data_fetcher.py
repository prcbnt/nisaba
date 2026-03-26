"""
data_fetcher.py — Téléchargement et normalisation des données de cours via yfinance.

Responsabilités :
- Téléchargement des cours de clôture ajustés pour TOUS les ETFs (macro + thématique) + SPY + EURUSD=X
  en un seul appel API (évite la double facturation de quotas yfinance).
- Conversion EUR→USD pour les ETFs Xetra
- Détection et signalement des données manquantes (aucune erreur silencieuse)
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import yaml
import yfinance as yf

logger = logging.getLogger(__name__)


class DataFetcher:
    def __init__(self, config_path: Path):
        config_path = Path(config_path)
        with open(config_path / "tickers.yaml") as f:
            self._ticker_cfg = yaml.safe_load(f)
        with open(config_path / "settings.yaml") as f:
            self._settings = yaml.safe_load(f)

        # Univers macro + thématique + satellite combinés (un seul appel yfinance)
        self.universe: list[dict] = self._ticker_cfg["universe"]
        self.universe_thematic: list[dict] = self._ticker_cfg.get("universe_thematic", [])
        self.universe_satellite: list[dict] = self._ticker_cfg.get("universe_satellite", [])
        self.eur_tickers: set[str] = set(self._ticker_cfg["eur_tickers"])
        self.benchmark: str = self._ticker_cfg["benchmark"]
        self.fx_ticker: str = self._ticker_cfg["fx_ticker"]
        self.fetch_period_days: int = self._settings["data"]["fetch_period_days"]

        # Tickers défensifs (un par stratégie, typiquement IEF)
        strategies = self._settings.get("strategies", {})
        self.defensive_tickers: list[str] = list({
            cfg.get("defensive_ticker")
            for cfg in strategies.values()
            if cfg.get("defensive_ticker")
        })

    # ──────────────────────────────────────────────────────────────────────────
    # API publique
    # ──────────────────────────────────────────────────────────────────────────

    def get_processed_prices(self, period_days: int | None = None) -> pd.DataFrame:
        """
        Retourne un DataFrame de cours de clôture ajustés, tous en USD.
        Colonnes = tickers (ETFs + SPY + EURUSD=X), index = dates de bourse.
        Lève une ValueError si un ticker est manquant ou invalide.
        """
        days = period_days or self.fetch_period_days
        raw = self._fetch_raw(days)
        converted = self._convert_eur_to_usd(raw)
        return converted

    # ──────────────────────────────────────────────────────────────────────────
    # Méthodes internes
    # ──────────────────────────────────────────────────────────────────────────

    def _fetch_raw(self, period_days: int) -> pd.DataFrame:
        start = (datetime.today() - timedelta(days=period_days)).strftime("%Y-%m-%d")
        all_tickers = (
            [etf["ticker"] for etf in self.universe]
            + [etf["ticker"] for etf in self.universe_thematic]
            + [etf["ticker"] for etf in self.universe_satellite]
            + self.defensive_tickers
            + [self.benchmark, self.fx_ticker]
        )
        all_tickers = list(dict.fromkeys(all_tickers))  # dédoublonnage, ordre préservé

        logger.info(f"Téléchargement de {len(all_tickers)} tickers depuis {start}…")

        raw = yf.download(
            all_tickers,
            start=start,
            auto_adjust=True,
            progress=False,
            threads=True,
        )

        # yfinance retourne un MultiIndex si plusieurs tickers
        if isinstance(raw.columns, pd.MultiIndex):
            data = raw["Close"]
        else:
            # Un seul ticker (ne devrait pas arriver ici)
            data = raw[["Close"]].rename(columns={"Close": all_tickers[0]})

        self._validate(data, all_tickers)
        return data

    def _validate(self, data: pd.DataFrame, expected_tickers: list[str]) -> None:
        """Lève une ValueError si un ticker est absent ou entièrement vide."""
        errors = []
        warnings = []

        for ticker in expected_tickers:
            if ticker not in data.columns:
                errors.append(f"  • {ticker} : absent de la réponse yfinance")
                continue

            series = data[ticker].dropna()
            if series.empty:
                errors.append(f"  • {ticker} : aucune donnée disponible")
                continue

            nan_pct = data[ticker].isna().sum() / max(len(data), 1)
            if nan_pct > 0.15:
                warnings.append(f"  • {ticker} : {nan_pct:.0%} de valeurs manquantes")

        if warnings:
            for w in warnings:
                logger.warning(w)

        if errors:
            msg = "Tickers invalides ou manquants :\n" + "\n".join(errors)
            raise ValueError(msg)

        logger.info(f"Validation OK — {len(data.columns)} séries, {len(data)} jours")

    def _convert_eur_to_usd(self, data: pd.DataFrame) -> pd.DataFrame:
        """Multiplie les cours EUR par le taux EURUSD pour uniformiser en USD."""
        data = data.copy()
        eurusd = data[self.fx_ticker].ffill()  # forward-fill les éventuels NaN du FX

        converted = []
        for ticker in self.eur_tickers:
            if ticker in data.columns:
                data[ticker] = data[ticker] * eurusd
                converted.append(ticker)

        if converted:
            logger.info(f"Conversion EUR→USD : {', '.join(converted)}")

        return data
