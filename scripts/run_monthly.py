#!/usr/bin/env python3
"""
run_monthly.py — Rapport mensuel de rebalancement Nisabā.

Exécuté le premier lundi de chaque mois (GitHub Actions détecte ce lundi
via la condition day-of-month 1–7 dans le workflow).
Contenu de l'email :
  - Stratégie Macro : signal REBALANCER / CONSERVER + Top 2 + classement 21 ETFs
  - Stratégie Thématique : signal REBALANCER / CONSERVER + Top 2 + classement 10 ETFs
  - Bouton CTA unique si au moins une stratégie nécessite un rebalancement

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
        fetcher = DataFetcher(CONFIG)

        scorer_macro     = MomentumScorer(CONFIG, strategy="macro")
        scorer_thematic  = MomentumScorer(CONFIG, strategy="thematic")
        portfolio_macro     = PortfolioManager(DATA / "portfolio_state.json", strategy="macro")
        portfolio_thematic  = PortfolioManager(DATA / "portfolio_state.json", strategy="thematic")

        # 1. Données (un seul appel pour les deux univers)
        logger.info("Étape 1/3 : téléchargement des cours…")
        prices = fetcher.get_processed_prices()

        # 2. Scores + Top 2 + allocations actuelles
        logger.info("Étape 2/3 : calcul des scores momentum…")
        ranked_macro    = scorer_macro.compute_scores(prices)
        top_n_macro     = scorer_macro.get_top_n(ranked_macro, n=2)
        current_macro   = portfolio_macro.get_current_allocation()
        needs_rb_macro  = portfolio_macro.needs_rebalancing(top_n_macro)

        ranked_thematic   = scorer_thematic.compute_scores(prices)
        top_n_thematic    = scorer_thematic.get_top_n(ranked_thematic, n=2)
        current_thematic  = portfolio_thematic.get_current_allocation()
        needs_rb_thematic = portfolio_thematic.needs_rebalancing(top_n_thematic)

        def _action(needs_rb, current):
            if not current:   return "INITIALISER"
            if needs_rb:      return "REBALANCER"
            return "CONSERVER"

        logger.info(f"[macro]     Signal : {_action(needs_rb_macro, current_macro)}")
        logger.info(f"[macro]     Top 2  : {[e['ticker'] for e in top_n_macro]}")
        logger.info(f"[thematic]  Signal : {_action(needs_rb_thematic, current_thematic)}")
        logger.info(f"[thematic]  Top 2  : {[e['ticker'] for e in top_n_thematic]}")

        # 3. Génération du rapport + envoi email
        logger.info("Étape 3/3 : envoi email…")
        pat = os.environ.get("CONFIRM_PAT", "").strip()
        confirm_url = f"{_CONFIRM_BASE_URL}#{pat}" if pat else None

        html = generate_monthly_report(
            ranked_macro=ranked_macro,
            top_n_macro=top_n_macro,
            current_macro=current_macro,
            ranked_thematic=ranked_thematic,
            top_n_thematic=top_n_thematic,
            current_thematic=current_thematic,
            run_date=date.today(),
            confirm_url=confirm_url,
        )

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
