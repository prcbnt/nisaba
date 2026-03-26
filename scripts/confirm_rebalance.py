#!/usr/bin/env python3
"""
confirm_rebalance.py — Confirmation de rebalancement (les deux stratégies).

À déclencher via GitHub Actions (workflow_dispatch) après avoir exécuté
le rebalancement de portefeuille chez le courtier. Ce script :
  1. Recalcule le Top 2 momentum du jour pour chaque stratégie
  2. Met à jour portfolio_state.json (macro + thématique)
  3. Envoie un email de confirmation récapitulatif
"""

import logging
import sys
from datetime import date
from pathlib import Path

import numpy as np

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
    logger.info(f"  Nisabā — Confirmation de rebalancement ({date.today()})")
    logger.info("═" * 60)

    sender = EmailSender(CONFIG)

    try:
        fetcher = DataFetcher(CONFIG)

        scorer_macro     = MomentumScorer(CONFIG, strategy="macro")
        scorer_thematic  = MomentumScorer(CONFIG, strategy="thematic")
        portfolio_macro     = PortfolioManager(DATA / "portfolio_state.json", strategy="macro")
        portfolio_thematic  = PortfolioManager(DATA / "portfolio_state.json", strategy="thematic")

        # 1. Données
        logger.info("Étape 1/3 : téléchargement des cours…")
        prices = fetcher.get_processed_prices()

        # 2. Scores + Top 2
        logger.info("Étape 2/3 : calcul des scores momentum…")

        ranked_macro  = scorer_macro.compute_scores(prices)
        top_n_macro   = scorer_macro.get_top_n(ranked_macro, n=2)
        old_macro     = portfolio_macro.get_current_allocation()

        ranked_thematic = scorer_thematic.compute_scores(prices)
        top_n_thematic  = scorer_thematic.get_top_n(ranked_thematic, n=2)
        old_thematic    = portfolio_thematic.get_current_allocation()

        # Substitution défensive si aucun ETF éligible (Antonacci)
        if not top_n_macro:
            logger.info("[macro]     Aucun ETF éligible — position défensive IEF")
            top_n_macro = [dict(_DEFENSIVE)]
        if not top_n_thematic:
            logger.info("[thematic]  Aucun ETF éligible — position défensive IEF")
            top_n_thematic = [dict(_DEFENSIVE)]

        # 3. Mise à jour des états
        portfolio_macro.update_allocation(top_n_macro)
        new_macro = portfolio_macro.get_current_allocation()

        portfolio_thematic.update_allocation(top_n_thematic)
        new_thematic = portfolio_thematic.get_current_allocation()

        logger.info(
            f"[macro]    {[h['ticker'] for h in old_macro] or ['(vide)']} "
            f"→ {[h['ticker'] for h in new_macro]}"
        )
        logger.info(
            f"[thematic] {[h['ticker'] for h in old_thematic] or ['(vide)']} "
            f"→ {[h['ticker'] for h in new_thematic]}"
        )

        # 4. Email de confirmation
        logger.info("Étape 3/3 : envoi de l'email de confirmation…")
        subject = f"Nisabā — Rebalancement confirmé ({date.today().strftime('%d/%m/%Y')})"
        html = _generate_confirmation_email(
            old_macro=[h["ticker"] for h in old_macro],
            new_macro=[h["ticker"] for h in new_macro],
            top_n_macro=top_n_macro,
            old_thematic=[h["ticker"] for h in old_thematic],
            new_thematic=[h["ticker"] for h in new_thematic],
            top_n_thematic=top_n_thematic,
            run_date=date.today(),
        )
        sender.send(subject, html)

        logger.info("✅ Rebalancement confirmé et email envoyé.")

    except Exception as exc:
        logger.error(f"❌ Échec : {exc}", exc_info=True)
        sender.send_alert(
            f"Erreur lors de la confirmation de rebalancement du {date.today()} :\n\n{exc}"
        )
        sys.exit(1)


def _pct(value, decimals: int = 1) -> str:
    try:
        if value is None or (isinstance(value, float) and np.isnan(value)):
            return "—"
        sign = "+" if value >= 0 else ""
        return f"{sign}{value * 100:.{decimals}f}%"
    except Exception:
        return "—"


def _allocation_rows(top_n: list[dict]) -> str:
    if not top_n:
        return '<tr><td colspan="5" style="color:#999;text-align:center;padding:12px;">Aucun ETF éligible — cash</td></tr>'
    n = len(top_n[:2])
    weight_pct = f"{100 // n}%"
    rows = ""
    for i, etf in enumerate(top_n[:2], 1):
        rows += f"""
        <tr>
          <td style="font-size:11px;color:#999;padding:7px 10px;">Top {i}</td>
          <td style="padding:7px 10px;"><strong>{etf['ticker']}</strong></td>
          <td style="font-size:11px;color:#555;padding:7px 10px;">{etf['name']}</td>
          <td style="text-align:right;padding:7px 10px;">{weight_pct}</td>
          <td style="text-align:right;font-weight:700;padding:7px 10px;">{_pct(etf.get('score'))}</td>
        </tr>"""
    return rows


def _generate_confirmation_email(
    old_macro: list[str],
    new_macro: list[str],
    top_n_macro: list[dict],
    old_thematic: list[str],
    new_thematic: list[str],
    top_n_thematic: list[dict],
    run_date: date,
) -> str:

    def _transition(old_t, new_t):
        old_str = ", ".join(old_t) if old_t else "Initialisation"
        new_str = ", ".join(new_t) if new_t else "(vide)"
        return old_str, new_str

    old_m_str, new_m_str   = _transition(old_macro, new_macro)
    old_th_str, new_th_str = _transition(old_thematic, new_thematic)

    macro_rows    = _allocation_rows(top_n_macro)
    thematic_rows = _allocation_rows(top_n_thematic)

    css = """
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
      max-width: 680px; margin: 0 auto; padding: 40px 24px;
      background: #fff; color: #000; font-size: 13px; line-height: 1.5;
    }
    .masthead { border-top: 4px solid #000; padding-top: 20px; margin-bottom: 40px; }
    .masthead-title { font-size: 22px; font-weight: 700; text-transform: uppercase; letter-spacing: -0.5px; }
    .masthead-sub { font-size: 12px; color: #555; margin-top: 4px; letter-spacing: 0.5px; text-transform: uppercase; }
    .signal { padding: 16px 20px; border-left: 4px solid #000; background: #f5f5f5; margin-bottom: 24px; }
    .signal-title { font-size: 14px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; }
    .signal-body { font-size: 12px; color: #333; margin-top: 6px; line-height: 1.7; }
    .strat-label {
      font-size: 11px; font-weight: 700; text-transform: uppercase;
      letter-spacing: 1.2px; border-top: 2px solid #000; padding-top: 10px;
      margin-top: 32px; margin-bottom: 16px;
    }
    .strat-label:first-of-type { margin-top: 0; }
    .section-label {
      font-size: 10px; font-weight: 700; text-transform: uppercase;
      letter-spacing: 1.5px; border-bottom: 1px solid #000; padding-bottom: 6px;
    }
    table { width: 100%; border-collapse: collapse; }
    th { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.8px;
         padding: 8px 10px; text-align: left; border-bottom: 1px solid #000; }
    td { border-bottom: 1px solid #e8e8e8; font-size: 12px; }
    tr:last-child td { border-bottom: none; }
    .footer {
      margin-top: 40px; padding-top: 12px; border-top: 1px solid #000;
      font-size: 10px; color: #999; text-transform: uppercase; letter-spacing: 0.5px;
    }
    """

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Nisabā — Rebalancement confirmé</title>
  <style>{css}</style>
</head>
<body>
  <div class="masthead">
    <div class="masthead-title">Nisabā</div>
    <div class="masthead-sub">Rebalancement confirmé &mdash; {run_date.strftime('%d/%m/%Y')}</div>
  </div>

  <div class="signal" style="margin-bottom:32px;">
    <div class="signal-title">✓ Portefeuilles mis à jour</div>
    <div class="signal-body">
      <code>portfolio_state.json</code> a été mis à jour et commité dans le dépôt GitHub.
    </div>
  </div>

  <!-- Macro -->
  <div class="strat-label" style="margin-top:0;">Stratégie Macro</div>

  <div class="signal" style="margin-bottom:16px;">
    <div class="signal-body">
      <span style="font-size:11px;color:#999;text-transform:uppercase;letter-spacing:0.5px;">Avant</span><br>
      {old_m_str}<br><br>
      <span style="font-size:11px;color:#999;text-transform:uppercase;letter-spacing:0.5px;">Après</span><br>
      <strong>{new_m_str}</strong>
    </div>
  </div>

  <div style="margin-bottom:32px;">
    <div class="section-label" style="margin-bottom:0;">Nouvelle allocation</div>
    <table>
      <thead><tr>
        <th>#</th><th>Ticker</th><th>Nom</th>
        <th style="text-align:right;">Poids</th>
        <th style="text-align:right;">Score</th>
      </tr></thead>
      <tbody>{macro_rows}</tbody>
    </table>
  </div>

  <!-- Thématique -->
  <div class="strat-label">Stratégie Thématique</div>

  <div class="signal" style="margin-bottom:16px;">
    <div class="signal-body">
      <span style="font-size:11px;color:#999;text-transform:uppercase;letter-spacing:0.5px;">Avant</span><br>
      {old_th_str}<br><br>
      <span style="font-size:11px;color:#999;text-transform:uppercase;letter-spacing:0.5px;">Après</span><br>
      <strong>{new_th_str}</strong>
    </div>
  </div>

  <div style="margin-bottom:32px;">
    <div class="section-label" style="margin-bottom:0;">Nouvelle allocation</div>
    <table>
      <thead><tr>
        <th>#</th><th>Ticker</th><th>Nom</th>
        <th style="text-align:right;">Poids</th>
        <th style="text-align:right;">Score</th>
      </tr></thead>
      <tbody>{thematic_rows}</tbody>
    </table>
  </div>

  <div class="footer">
    Nisabā &mdash; {run_date.strftime('%d/%m/%Y')} &mdash; Confirmation de rebalancement
  </div>
</body>
</html>"""


if __name__ == "__main__":
    main()
