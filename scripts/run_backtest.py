#!/usr/bin/env python3
"""
run_backtest.py — Backtest de la stratégie momentum sur données historiques.

Usage :
    python scripts/run_backtest.py
    python scripts/run_backtest.py --start 2018-01-01 --end 2024-12-31

Produit :
    - Résumé dans le terminal (total return, CAGR, alpha, max drawdown)
    - Fichier CSV exporté dans data/backtest_results.csv
"""

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import yaml
from src.backtester import Backtester

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

CONFIG = ROOT / "config"
DATA = ROOT / "data"


def parse_args() -> argparse.Namespace:
    with open(CONFIG / "settings.yaml") as f:
        settings = yaml.safe_load(f)
    default_start = settings["backtest"]["default_start"]

    parser = argparse.ArgumentParser(
        description="Backtest de la stratégie Nisabā (50% M1 + 50% M3, filtre MM200j)"
    )
    parser.add_argument(
        "--start",
        default=default_start,
        help=f"Date de début (YYYY-MM-DD, défaut : {default_start})",
    )
    parser.add_argument(
        "--end",
        default=None,
        help="Date de fin (YYYY-MM-DD, défaut : aujourd'hui)",
    )
    parser.add_argument(
        "--csv",
        default=str(DATA / "backtest_results.csv"),
        help="Chemin du fichier CSV de sortie",
    )
    return parser.parse_args()


def print_stats(stats: dict) -> None:
    sep = "═" * 55
    print(f"\n{sep}")
    print(f"  RÉSULTATS DU BACKTEST — {stats['period']}")
    print(sep)
    print(f"  {'Durée (mois)':<38} {stats['n_months']}")
    print()
    print(f"  {'Stratégie — Total Return':<38} {stats['portfolio_total_return']:+.1%}")
    print(f"  {'S&P 500  — Total Return':<38} {stats['spy_total_return']:+.1%}")
    print()
    print(f"  {'Stratégie — CAGR':<38} {stats['portfolio_cagr']:+.1%}")
    print(f"  {'S&P 500  — CAGR':<38} {stats['spy_cagr']:+.1%}")
    print()
    alpha = stats["alpha_annualized"]
    alpha_sign = "+" if alpha >= 0 else ""
    print(f"  {'Alpha annualisé':<38} {alpha_sign}{alpha:.1%}")
    print(f"  {'Max Drawdown (stratégie)':<38} {stats['max_drawdown']:.1%}")
    print(sep)


def main() -> None:
    args = parse_args()

    logger.info("═" * 60)
    logger.info(f"  Nisabā — Backtest {args.start} → {args.end or 'aujourd'hui'}")
    logger.info("═" * 60)

    bt = Backtester(config_path=CONFIG)
    result = bt.run(start_date=args.start, end_date=args.end)

    if "error" in result:
        logger.error(result["error"])
        sys.exit(1)

    # Affichage des stats
    print_stats(result["stats"])

    # Export CSV
    csv_path = Path(args.csv)
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    combined = result["portfolio"].join(result["spy"], lsuffix="_strategie", rsuffix="_spy")
    combined.to_csv(csv_path)
    print(f"\n  Résultats exportés → {csv_path}\n")

    # Rapport des derniers rebalancements
    history = result.get("history", [])
    if history:
        print("  Derniers rebalancements :")
        for entry in history[-6:]:
            tickers = ", ".join(h["ticker"] for h in entry["holdings"]) or "CASH"
            print(f"    {entry['date']}  →  {tickers}")
        print()


if __name__ == "__main__":
    main()
