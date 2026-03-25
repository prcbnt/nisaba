#!/usr/bin/env python3
"""
run_weekly.py — Rapport hebdomadaire Nisabā.

Exécuté chaque lundi (sauf le premier lundi du mois, géré par run_monthly.py).
Contenu de l'email :
  - Portfolio Allocation : comparaison allocation actuelle vs cible + signal rebalancement
  - Classement momentum complet des 21 ETFs
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


def main() -> None:
    logger.info("═" * 60)
    logger.info(f"  Nisabā — Rapport hebdomadaire ({date.today()})")
    logger.info("═" * 60)

    sender = EmailSender(CONFIG)

    try:
        fetcher   = DataFetcher(CONFIG)
        scorer    = MomentumScorer(CONFIG)
        portfolio = PortfolioManager(DATA / "portfolio_state.json")

        # 1. Données
        logger.info("Étape 1/3 : téléchargement des cours…")
        prices = fetcher.get_processed_prices()

        # 2. Scores + Top 2 + allocation actuelle
        logger.info("Étape 2/3 : calcul des scores momentum…")
        ranked  = scorer.compute_scores(prices)
        top_n   = scorer.get_top_n(ranked, n=2)
        current = portfolio.get_current_allocation()

        # SPY performance M1
        spy_series = prices["SPY"].dropna()
        spy_ret_1m = (
            float(spy_series.iloc[-1] / spy_series.iloc[-22] - 1)
            if len(spy_series) >= 22 else None
        )

        # 3. Génération et envoi
        logger.info("Étape 3/3 : envoi de l'email…")
        pat = os.environ.get("CONFIRM_PAT", "").strip()
        confirm_url = f"{_CONFIRM_BASE_URL}#{pat}" if pat else None
        html = generate_weekly_report(ranked, top_n, current, spy_ret_1m, date.today(), confirm_url=confirm_url)
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
