#!/usr/bin/env python3
"""
run_monthly.py — Rapport mensuel de rebalancement Nisabā.

Exécuté le premier lundi de chaque mois (GitHub Actions détecte ce lundi
via la condition day-of-month 1–7 dans le workflow).
Contenu de l'email :
  - Signal REBALANCER / CONSERVER / INITIALISER
  - Nouveau Top 1 / Top 2 avec score détaillé
  - Classement complet des 21 ETFs
"""

import logging
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.data_fetcher import DataFetcher
from src.email_sender import EmailSender
from src.momentum_scorer import MomentumScorer
from src.portfolio import PortfolioManager
from src.report_generator import generate_monthly_report

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
    logger.info(f"  Nisabā — Rebalancement mensuel ({date.today()})")
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
        top_n = scorer.get_top_n(ranked, n=2)

        # 3. Comparaison avec allocation actuelle
        logger.info("Étape 3/4 : comparaison avec l'allocation en cours…")
        current = portfolio.get_current_allocation()
        needs_rb = portfolio.needs_rebalancing(top_n)
        action = "REBALANCER" if needs_rb else "CONSERVER"
        if not current:
            action = "INITIALISER"

        logger.info(f"Signal : {action}")
        if top_n:
            logger.info(f"Nouveau Top 2 : {[e['ticker'] for e in top_n]}")

        # 4. Mise à jour de l'état + email
        logger.info("Étape 4/4 : mise à jour état + envoi email…")
        html = generate_monthly_report(ranked, top_n, current, date.today())

        # Mise à jour AVANT l'envoi pour qu'en cas d'erreur email l'état soit correct
        if top_n:
            portfolio.update_allocation(top_n)

        month_fr = {
            1: "Janvier", 2: "Février", 3: "Mars", 4: "Avril",
            5: "Mai", 6: "Juin", 7: "Juillet", 8: "Août",
            9: "Septembre", 10: "Octobre", 11: "Novembre", 12: "Décembre"
        }[date.today().month]
        subject = f"📅 Nisabā — Rebalancement {month_fr} {date.today().year}"
        sender.send(subject, html)

        logger.info("✅ Rapport mensuel envoyé avec succès.")

    except Exception as exc:
        logger.error(f"❌ Échec du pipeline : {exc}", exc_info=True)
        sender.send_alert(
            f"Erreur lors du rapport mensuel du {date.today()} :\n\n{exc}"
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
