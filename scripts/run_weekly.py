#!/usr/bin/env python3
"""
run_weekly.py — Rapport hebdomadaire Nisabā.

Exécuté chaque lundi (sauf le premier lundi du mois, géré par run_monthly.py).
Contenu de l'email :
  - Tableau récapitulatif (toutes stratégies + benchmarks SPY/IEF)
  - Stratégie Macro : signal + allocation actuelle vs cible + classement 21 ETFs
  - Stratégie Thématique : signal + allocation actuelle vs cible + classement 10 ETFs
  - Satellite (DBMF) : signal + allocation
"""

import logging
import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.data_fetcher import DataFetcher
from src.email_sender import EmailSender
from src.momentum_scorer import MomentumScorer
from src.portfolio import PortfolioManager
from src.report_generator import _CONFIRM_BASE_URL, generate_weekly_report

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

CONFIG = ROOT / "config"
DATA   = ROOT / "data"

# Position défensive : utilisée quand aucun ETF ne passe le filtre MA (Antonacci)
_DEFENSIVE = {
    "ticker": "IEF",
    "name": "iShares 7-10 Year Treasury Bond ETF",
    "sector": "Obligations",
    "region": "Défensif",
    "score": None,
    "ret_1m": None,
    "ret_3m": None,
    "ret_6m": None,
    "above_ma": True,
    "current_price": None,
    "ma": None,
    "status": "✓",
    "_defensive": True,
}


def main() -> None:
    logger.info("═" * 60)
    logger.info(f"  Nisabā — Rapport hebdomadaire ({date.today()})")
    logger.info("═" * 60)

    sender = EmailSender(CONFIG)

    try:
        import yaml
        with open(CONFIG / "settings.yaml") as f:
            settings = yaml.safe_load(f)
        portfolio_weights = {
            s: cfg.get("portfolio_weight", 1/3)
            for s, cfg in settings.get("strategies", {}).items()
        }

        fetcher = DataFetcher(CONFIG)

        scorer_macro      = MomentumScorer(CONFIG, strategy="macro")
        scorer_thematic   = MomentumScorer(CONFIG, strategy="thematic")
        scorer_satellite  = MomentumScorer(CONFIG, strategy="satellite")
        portfolio_macro     = PortfolioManager(DATA / "portfolio_state.json", strategy="macro")
        portfolio_thematic  = PortfolioManager(DATA / "portfolio_state.json", strategy="thematic")
        portfolio_satellite = PortfolioManager(DATA / "portfolio_state.json", strategy="satellite")

        # 1. Données (un seul appel pour tous les univers)
        logger.info("Étape 1/3 : téléchargement des cours…")
        prices = fetcher.get_processed_prices()

        # 2. Scores + Top N + allocations actuelles
        logger.info("Étape 2/3 : calcul des scores momentum…")
        ranked_macro    = scorer_macro.compute_scores(prices)
        top_n_macro     = scorer_macro.get_top_n(ranked_macro, n=2)
        current_macro   = portfolio_macro.get_current_allocation()

        ranked_thematic   = scorer_thematic.compute_scores(prices)
        top_n_thematic    = scorer_thematic.get_top_n(ranked_thematic, n=2)
        current_thematic  = portfolio_thematic.get_current_allocation()

        ranked_satellite  = scorer_satellite.compute_scores(prices)
        top_n_satellite   = scorer_satellite.get_top_n(ranked_satellite, n=1)
        current_satellite = portfolio_satellite.get_current_allocation()

        # Substitution défensive si aucun ETF éligible (Antonacci)
        if not top_n_macro:
            logger.info("[macro]     Aucun ETF éligible — position défensive IEF")
            top_n_macro = [dict(_DEFENSIVE)]
        if not top_n_thematic:
            logger.info("[thematic]  Aucun ETF éligible — position défensive IEF")
            top_n_thematic = [dict(_DEFENSIVE)]
        # Satellite : DBMF toujours présent (filtre désactivé), pas de fallback nécessaire

        logger.info(f"[macro]     Top 2 : {[e['ticker'] for e in top_n_macro]}")
        logger.info(f"[thematic]  Top 2 : {[e['ticker'] for e in top_n_thematic]}")
        logger.info(f"[satellite] Top 1 : {[e['ticker'] for e in top_n_satellite]}")

        # Performance 1S des positions actuelles
        perf_macro     = portfolio_macro.compute_weekly_performance(prices)
        perf_thematic  = portfolio_thematic.compute_weekly_performance(prices)
        perf_satellite = portfolio_satellite.compute_weekly_performance(prices)

        # Benchmarks 1S
        _DAYS_1W = 6  # 5 jours de bourse + 1
        spy_series = prices["SPY"].dropna()
        ief_series = prices["IEF"].dropna()
        spy_ret_1w = (
            float(spy_series.iloc[-1] / spy_series.iloc[-_DAYS_1W] - 1)
            if len(spy_series) >= _DAYS_1W else None
        )
        ief_ret_1w = (
            float(ief_series.iloc[-1] / ief_series.iloc[-_DAYS_1W] - 1)
            if len(ief_series) >= _DAYS_1W else None
        )

        # 3. Génération et envoi
        logger.info("Étape 3/3 : envoi de l'email…")
        pat = os.environ.get("CONFIRM_PAT", "").strip()
        confirm_url = f"{_CONFIRM_BASE_URL}#{pat}" if pat else None

        html = generate_weekly_report(
            ranked_macro=ranked_macro,
            top_n_macro=top_n_macro,
            current_macro=current_macro,
            perf_macro=perf_macro,
            ranked_thematic=ranked_thematic,
            top_n_thematic=top_n_thematic,
            current_thematic=current_thematic,
            perf_thematic=perf_thematic,
            ranked_satellite=ranked_satellite,
            top_n_satellite=top_n_satellite,
            current_satellite=current_satellite,
            perf_satellite=perf_satellite,
            spy_ret_1w=spy_ret_1w,
            ief_ret_1w=ief_ret_1w,
            portfolio_weights=portfolio_weights,
            run_date=date.today(),
            confirm_url=confirm_url,
        )
        subject = f"Nisabā — {date.today().strftime('%d/%m/%Y')}"
        sender.send(subject, html)

        logger.info("✅ Rapport hebdomadaire envoyé avec succès.")

    except Exception as exc:
        logger.error(f"❌ Échec du pipeline : {exc}", exc_info=True)
        sender.send_alert(
            f"Erreur lors du rapport hebdomadaire du {date.today()} :\n\n{exc}"
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
