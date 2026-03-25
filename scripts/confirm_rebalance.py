#!/usr/bin/env python3
"""
confirm_rebalance.py — Confirmation de rebalancement.

À déclencher via GitHub Actions (workflow_dispatch) après avoir exécuté
le rebalancement de portefeuille chez le courtier. Ce script :
  1. Recalcule le Top 2 momentum du jour
  2. Met à jour portfolio_state.json avec la nouvelle allocation
  3. Envoie un email de confirmation récapitulatif
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
    logger.info(f"  Nisabā — Confirmation de rebalancement ({date.today()})")
    logger.info("═" * 60)

    sender = EmailSender(CONFIG)

    try:
        fetcher   = DataFetcher(CONFIG)
        scorer    = MomentumScorer(CONFIG)
        portfolio = PortfolioManager(DATA / "portfolio_state.json")

        # 1. Données
        logger.info("Étape 1/3 : téléchargement des cours…")
        prices = fetcher.get_processed_prices()

        # 2. Scores + Top 2
        logger.info("Étape 2/3 : calcul des scores momentum…")
        ranked = scorer.compute_scores(prices)
        top_n  = scorer.get_top_n(ranked, n=2)

        old = portfolio.get_current_allocation()
        old_tickers = [h["ticker"] for h in old] if old else []

        # 3. Mise à jour de l'état
        portfolio.update_allocation(top_n)
        new = portfolio.get_current_allocation()
        new_tickers = [h["ticker"] for h in new] if new else []

        logger.info(
            f"Portefeuille mis à jour : "
            f"{old_tickers or ['(vide)']} → {new_tickers or ['(vide)']}"
        )

        # 4. Email de confirmation
        logger.info("Étape 3/3 : envoi de l'email de confirmation…")
        subject = f"Nisabā — Rebalancement confirmé ({date.today().strftime('%d/%m/%Y')})"
        html = _generate_confirmation_email(old_tickers, new_tickers, top_n, date.today())
        sender.send(subject, html)

        logger.info("✅ Rebalancement confirmé et email envoyé.")

    except Exception as exc:
        logger.error(f"❌ Échec : {exc}", exc_info=True)
        sender.send_alert(
            f"Erreur lors de la confirmation de rebalancement du {date.today()} :\n\n{exc}"
        )
        sys.exit(1)


def _generate_confirmation_email(
    old_tickers: list,
    new_tickers: list,
    top_n: list,
    run_date: date,
) -> str:
    import numpy as np

    def _pct(value, decimals: int = 1) -> str:
        try:
            if value is None or (isinstance(value, float) and np.isnan(value)):
                return "—"
            sign = "+" if value >= 0 else ""
            return f"{sign}{value * 100:.{decimals}f}%"
        except Exception:
            return "—"

    rows = ""
    for i, etf in enumerate(top_n[:2], 1):
        rows += f"""
        <tr>
          <td style="font-size:11px;color:#999;padding:7px 10px;">Top {i}</td>
          <td style="padding:7px 10px;"><strong>{etf['ticker']}</strong></td>
          <td style="font-size:11px;color:#555;padding:7px 10px;">{etf['name']}</td>
          <td style="text-align:right;padding:7px 10px;">50%</td>
          <td style="text-align:right;font-weight:700;padding:7px 10px;">{_pct(etf.get('score'))}</td>
        </tr>"""

    if not rows:
        rows = '<tr><td colspan="5" style="color:#999;text-align:center;padding:12px;">Aucun ETF éligible — cash</td></tr>'

    old_str = ", ".join(old_tickers) if old_tickers else "Initialisation"
    new_str = ", ".join(new_tickers) if new_tickers else "(vide)"

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Nisabā — Rebalancement confirmé</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
      max-width: 600px; margin: 0 auto; padding: 40px 24px;
      background: #fff; color: #000; font-size: 13px; line-height: 1.5;
    }}
    .masthead {{ border-top: 4px solid #000; padding-top: 20px; margin-bottom: 40px; }}
    .masthead-title {{ font-size: 22px; font-weight: 700; text-transform: uppercase; letter-spacing: -0.5px; }}
    .masthead-sub {{ font-size: 12px; color: #555; margin-top: 4px; letter-spacing: 0.5px; text-transform: uppercase; }}
    .signal {{ padding: 16px 20px; border-left: 4px solid #000; background: #f5f5f5; margin-bottom: 28px; }}
    .signal-title {{ font-size: 14px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; }}
    .signal-body {{ font-size: 12px; color: #333; margin-top: 6px; line-height: 1.7; }}
    .section-label {{
      font-size: 10px; font-weight: 700; text-transform: uppercase;
      letter-spacing: 1.5px; border-bottom: 1px solid #000; padding-bottom: 6px;
    }}
    table {{ width: 100%; border-collapse: collapse; }}
    th {{ font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.8px;
         padding: 8px 10px; text-align: left; border-bottom: 1px solid #000; }}
    td {{ border-bottom: 1px solid #e8e8e8; font-size: 12px; }}
    tr:last-child td {{ border-bottom: none; }}
    .footer {{
      margin-top: 40px; padding-top: 12px; border-top: 1px solid #000;
      font-size: 10px; color: #999; text-transform: uppercase; letter-spacing: 0.5px;
    }}
  </style>
</head>
<body>
  <div class="masthead">
    <div class="masthead-title">Nisabā</div>
    <div class="masthead-sub">Rebalancement confirmé &mdash; {run_date.strftime('%d/%m/%Y')}</div>
  </div>

  <div class="signal" style="margin-bottom:32px;">
    <div class="signal-title">✓ Portefeuille mis à jour</div>
    <div class="signal-body">
      <span style="font-size:11px;color:#999;text-transform:uppercase;letter-spacing:0.5px;">Avant</span><br>
      {old_str}<br><br>
      <span style="font-size:11px;color:#999;text-transform:uppercase;letter-spacing:0.5px;">Après</span><br>
      <strong>{new_str}</strong>
    </div>
  </div>

  <div style="margin-bottom:28px;">
    <div class="section-label" style="margin-bottom:0;">Nouvelle allocation</div>
    <table>
      <thead><tr>
        <th>#</th><th>Ticker</th><th>Nom</th>
        <th style="text-align:right;">Poids</th>
        <th style="text-align:right;">Score</th>
      </tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </div>

  <p style="font-size:11px;color:#555;line-height:1.6;">
    <code>portfolio_state.json</code> a été mis à jour et commité dans le dépôt GitHub.
  </p>

  <div class="footer">
    Nisabā &mdash; {run_date.strftime('%d/%m/%Y')} &mdash; Confirmation de rebalancement
  </div>
</body>
</html>"""


if __name__ == "__main__":
    main()
