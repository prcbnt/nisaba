#!/usr/bin/env python3
"""
run_weekly.py — Rapport hebdomadaire Nisabā.

Exécuté chaque lundi (sauf le premier lundi du mois, géré par run_monthly.py).
Contenu de l'email :
  - Performance 7j du Top 1 / Top 2 vs SPY
  - Classement momentum complet des 21 ETFs
"""

import logging
import sys
from datetime import date
from pathlib import Path

# Ajout du répertoire racine au PYTHONPATH
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.data_fetcher import DataFetcher
from src.email_sender import EmailSender
from src.momentum_scorer import MomentumScorer
from src.portfolio import PortfolioManager
from src.report_generator import generate_weekly_report

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

CONFIG = ROOT / "config"
DATA = ROOT / "data"


def main() -> None:
    logger.info("═" * 60)
    logger.info(f"  Nisabā — Rapport hebdomadaire ({date.today()})")
    logger.info("═" * 60)

    sender = EmailSender(CONFIG)

    try:
        fetcher = DataFetcher(CONFIG)
        scorer = MomentumScorer(CONFIG)
        portfolio = PortfolioManager(DATA / "portfolio_state.json")

        # 1. Données
        logger.info("Étape 1/4 : téléchargement des cours…")
        prices = fetcher.get_processed_prices()

        # 2. Scores
        logger.info("Étape 2/4 : calcul des scores momentum…")
        ranked = scorer.compute_scores(prices)

        # 3. Performance hebdomadaire
        logger.info("Étape 3/4 : calcul de la performance 7j…")
        weekly_perf = portfolio.compute_weekly_performance(prices)
        spy_series = prices["SPY"].dropna()
        spy_ret_1w = (
            float(spy_series.iloc[-1] / spy_series.iloc[-6] - 1)
            if len(spy_series) >= 6
            else None
        )

        # 4. Génération et envoi de l'email
        logger.info("Étape 4/4 : envoi de l'email…")
        html = generate_weekly_report(ranked, weekly_perf, spy_ret_1w, date.today())
        subject = f"📊 Nisabā — Hebdomadaire {date.today().strftime('%d/%m/%Y')}"
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
