#!/usr/bin/env python3
"""
run_monthly.py — Rapport mensuel de rebalancement Nisabā.

Exécuté le premier lundi de chaque mois (GitHub Actions détecte ce lundi
via la condition day-of-month 1–7 dans le workflow).
Contenu de l'email :
  - Signal REBALANCER / CONSERVER / INITIALISER
  - Nouveau Top 1 / Top 2 avec score détaillé
  - Classement complet des 21 ETFs
  - Bouton CTA "Confirmer le rebalancement" (1-clic via GitHub Pages)

Note : portfolio_state.json n'est PAS mis à jour ici.
       Il le sera uniquement quand tu cliqueras "Confirmer le rebalancement"
       dans l'email → confirm_rebalance.yml → confirm_rebalance.py.
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
from src.report_generator import _CONFIRM_BASE_URL, generate_monthly_report

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
    logger.info(f"  Nisabā — Rebalancement mensuel ({date.today()})")
    logger.info("═" * 60)

    sender = EmailSender(CONFIG)

    try:
        fetcher   = DataFetcher(CONFIG)
        scorer    = MomentumScorer(CONFIG)
        portfolio = PortfolioManager(DATA / "portfolio_state.json")

        # 1. Données
        logger.info("Étape 1/3 : téléchargement des cours…")
        prices = fetcher.get_processed_prices()

        # 2. Scores
        logger.info("Étape 2/3 : calcul des scores momentum…")
        ranked   = scorer.compute_scores(prices)
        top_n    = scorer.get_top_n(ranked, n=2)
        current  = portfolio.get_current_allocation()
        needs_rb = portfolio.needs_rebalancing(top_n)

        action = "REBALANCER" if needs_rb else "CONSERVER"
        if not current:
            action = "INITIALISER"

        logger.info(f"Signal : {action}")
        if top_n:
            logger.info(f"Nouveau Top 2 : {[e['ticker'] for e in top_n]}")

        # 3. Génération du rapport + envoi email
        logger.info("Étape 3/3 : envoi email…")
        pat = os.environ.get("CONFIRM_PAT", "").strip()
        confirm_url = f"{_CONFIRM_BASE_URL}#{pat}" if pat else None
        html = generate_monthly_report(ranked, top_n, current, date.today(), confirm_url=confirm_url)

        month_fr = {
            1: "Janvier", 2: "Février", 3: "Mars", 4: "Avril",
            5: "Mai", 6: "Juin", 7: "Juillet", 8: "Août",
            9: "Septembre", 10: "Octobre", 11: "Novembre", 12: "Décembre"
        }[date.today().month]
        subject = f"Nisabā — Rebalancement {month_fr} {date.today().year}"
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
