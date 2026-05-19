#!/usr/bin/env python3
"""
run_daily.py — Suivi quotidien Nisabā (mar–ven, hors lundi).

Contenu de l'email :
  - Tableau récapitulatif par stratégie : positions actuelles, perf J-1,
    perf depuis entrée (entry_date)
  - Benchmarks SPY et IEF (J-1)

Note : pas de calcul de scores momentum, pas de rebalancement.
       Ce script ne modifie pas portfolio_state.json.
"""

import logging
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.data_fetcher import DataFetcher
from src.email_sender import EmailSender
from src.portfolio import PortfolioManager
from src.report_generator import generate_daily_report

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
    logger.info(f"  Nisabā — Suivi quotidien ({date.today()})")
    logger.info("═" * 60)

    sender = EmailSender(CONFIG)

    try:
        import yaml
        with open(CONFIG / "settings.yaml") as f:
            settings = yaml.safe_load(f)
        portfolio_weights = {
            s: cfg.get("portfolio_weight", 1 / 3)
            for s, cfg in settings.get("strategies", {}).items()
        }

        fetcher = DataFetcher(CONFIG)

        portfolio_macro     = PortfolioManager(DATA / "portfolio_state.json", strategy="macro")
        portfolio_thematic  = PortfolioManager(DATA / "portfolio_state.json", strategy="thematic")
        portfolio_satellite = PortfolioManager(DATA / "portfolio_state.json", strategy="satellite")

        # 1. Données de marché
        logger.info("Étape 1/2 : téléchargement des cours…")
        prices = fetcher.get_processed_prices()

        # 2. Perf J-1 + depuis entrée par stratégie
        logger.info("Étape 2/2 : calcul des performances…")
        perf_macro     = portfolio_macro.compute_daily_performance(prices)
        perf_thematic  = portfolio_thematic.compute_daily_performance(prices)
        perf_satellite = portfolio_satellite.compute_daily_performance(prices)

        logger.info(f"[macro]     {list(perf_macro.keys()) or ['(vide)']}")
        logger.info(f"[thematic]  {list(perf_thematic.keys()) or ['(vide)']}")
        logger.info(f"[satellite] {list(perf_satellite.keys()) or ['(vide)']}")

        # Benchmarks J-1
        spy_series = prices["SPY"].dropna()
        ief_series = prices["IEF"].dropna()
        spy_ret_1d = (
            float(spy_series.iloc[-1] / spy_series.iloc[-2] - 1)
            if len(spy_series) >= 2 else None
        )
        ief_ret_1d = (
            float(ief_series.iloc[-1] / ief_series.iloc[-2] - 1)
            if len(ief_series) >= 2 else None
        )

        html = generate_daily_report(
            perf_macro=perf_macro,
            perf_thematic=perf_thematic,
            perf_satellite=perf_satellite,
            portfolio_weights=portfolio_weights,
            spy_ret_1d=spy_ret_1d,
            ief_ret_1d=ief_ret_1d,
            run_date=date.today(),
        )

        subject = f"Nisabā — {date.today().strftime('%d/%m/%Y')}"
        sender.send(subject, html)

        logger.info("✅ Suivi quotidien envoyé.")

    except Exception as exc:
        logger.error(f"❌ Échec : {exc}", exc_info=True)
        sender.send_alert(
            f"Erreur lors du suivi quotidien du {date.today()} :\n\n{exc}"
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
