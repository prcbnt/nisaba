#!/usr/bin/env python3
"""
run_weekly.py — Rapport hebdomadaire Nisabā.

Exécuté chaque lundi (sauf le premier lundi du mois, géré par run_monthly.py).
Contenu de l'email :
  - Stratégie Macro : signal + allocation actuelle vs cible + classement 21 ETFs
  - Stratégie Thématique : signal + allocation actuelle vs cible + classement 10 ETFs
  - Bouton CTA unique si au moins une stratégie nécessite un rebalancement
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

        ranked_thematic   = scorer_thematic.compute_scores(prices)
        top_n_thematic    = scorer_thematic.get_top_n(ranked_thematic, n=2)
        current_thematic  = portfolio_thematic.get_current_allocation()

        # Substitution défensive si aucun ETF éligible (Antonacci)
        if not top_n_macro:
            logger.info("[macro]     Aucun ETF éligible — position défensive IEF")
            top_n_macro = [dict(_DEFENSIVE)]
        if not top_n_thematic:
            logger.info("[thematic]  Aucun ETF éligible — position défensive IEF")
            top_n_thematic = [dict(_DEFENSIVE)]

        logger.info(f"[macro]     Top 2 : {[e['ticker'] for e in top_n_macro]}")
        logger.info(f"[thematic]  Top 2 : {[e['ticker'] for e in top_n_thematic]}")

        # SPY performance M1 (benchmark macro)
        spy_series = prices["SPY"].dropna()
        spy_ret_1m = (
            float(spy_series.iloc[-1] / spy_series.iloc[-22] - 1)
            if len(spy_series) >= 22 else None
        )

        # 3. Génération et envoi
        logger.info("Étape 3/3 : envoi de l'email…")
        pat = os.environ.get("CONFIRM_PAT", "").strip()
        confirm_url = f"{_CONFIRM_BASE_URL}#{pat}" if pat else None

        html = generate_weekly_report(
            ranked_macro=ranked_macro,
            top_n_macro=top_n_macro,
            current_macro=current_macro,
            spy_ret_1m=spy_ret_1m,
            ranked_thematic=ranked_thematic,
            top_n_thematic=top_n_thematic,
            current_thematic=current_thematic,
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
