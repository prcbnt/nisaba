"""
report_generator.py — Génération des emails HTML (hebdomadaire et mensuel).

Design : Swiss / International Typographic Style.
         Helvetica, noir et blanc, grille stricte, typographie forte.
"""

from datetime import date

import numpy as np
import pandas as pd

# URL de base de la page GitHub Pages de confirmation (1-clic depuis l'email)
# Le PAT est ajouté comme fragment (#TOKEN) par les scripts — jamais envoyé au serveur.
_CONFIRM_BASE_URL = "https://prcbnt.github.io/nisaba/confirm.html"


# ──────────────────────────────────────────────────────────────────────────────
# Helpers de formatage
# ──────────────────────────────────────────────────────────────────────────────

def _ht(ticker: str) -> str:
    """Échappe le point des tickers (ex. EXV6.DE → EXV6&#46;DE).

    Les clients email (Gmail…) auto-détectent 'XYZ.DE' comme un nom de
    domaine et créent un lien hypertexte indésirable. Remplacer '.' par
    l'entité HTML &#46; produit un rendu identique sans déclencher la détection.
    """
    return ticker.replace('.', '&#46;')


def _pct(value, decimals: int = 1) -> str:
    try:
        if value is None or (isinstance(value, float) and np.isnan(value)):
            return "—"
        sign = "+" if value >= 0 else ""
        return f"{sign}{value * 100:.{decimals}f}%"
    except Exception:
        return "—"


def _cta_button(confirm_url: str | None) -> str:
    """
    Bouton CTA 'Confirmer le rebalancement'.

    confirm_url doit être la page GitHub Pages avec le PAT en fragment :
      https://prcbnt.github.io/nisaba/confirm.html#ghp_xxxxx

    Si confirm_url est None (PAT absent), le bouton est masqué.
    """
    if not confirm_url:
        return ""
    return f"""
    <div class="cta-wrap">
      <a class="cta-btn" href="{confirm_url}" target="_blank">
        Confirmer le rebalancement
      </a>
      <div class="cta-hint">
        À cliquer après avoir exécuté les ordres chez votre courtier.
        Met à jour <code>portfolio_state.json</code> automatiquement.
      </div>
    </div>"""


def _weight(value) -> str:
    """Gras si positif, normal si négatif — pas de couleur."""
    try:
        if value is None or (isinstance(value, float) and np.isnan(value)):
            return "font-weight:400;color:#999;"
        return "font-weight:700;" if value >= 0 else "font-weight:400;color:#555;"
    except Exception:
        return "font-weight:400;"


# ──────────────────────────────────────────────────────────────────────────────
# CSS Swiss
# ──────────────────────────────────────────────────────────────────────────────

_BASE_CSS = """
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
    max-width: 800px;
    margin: 0 auto;
    padding: 40px 24px;
    background: #fff;
    color: #000;
    font-size: 13px;
    line-height: 1.5;
    -webkit-font-smoothing: antialiased;
  }
  .masthead {
    border-top: 4px solid #000;
    padding-top: 20px;
    margin-bottom: 40px;
  }
  .masthead-title {
    font-size: 22px;
    font-weight: 700;
    letter-spacing: -0.5px;
    text-transform: uppercase;
  }
  .masthead-sub {
    font-size: 12px;
    color: #555;
    margin-top: 4px;
    letter-spacing: 0.5px;
    text-transform: uppercase;
  }
  .section {
    margin-bottom: 36px;
  }
  .section-label {
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    color: #000;
    border-bottom: 1px solid #000;
    padding-bottom: 6px;
    margin-bottom: 0;
  }
  table {
    width: 100%;
    border-collapse: collapse;
  }
  th {
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    padding: 8px 10px;
    text-align: left;
    border-bottom: 1px solid #000;
    background: #fff;
    color: #000;
  }
  th.num { text-align: right; }
  td {
    padding: 7px 10px;
    font-size: 12px;
    border-bottom: 1px solid #e8e8e8;
    vertical-align: middle;
  }
  td.num { text-align: right; font-variant-numeric: tabular-nums; }
  tr:last-child td { border-bottom: none; }
  .signal {
    padding: 16px 20px;
    margin-bottom: 8px;
    border-left: 4px solid #000;
    background: #f5f5f5;
  }
  .signal-title {
    font-size: 14px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
  .signal-body {
    font-size: 12px;
    color: #333;
    margin-top: 4px;
  }
  .signal.invert {
    background: #000;
    color: #fff;
  }
  .signal.invert .signal-body { color: #ccc; }
  .top-block {
    padding: 16px 0;
    border-bottom: 1px solid #e8e8e8;
  }
  .top-block:last-child { border-bottom: none; }
  .top-rank {
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: #999;
  }
  .top-ticker {
    font-size: 20px;
    font-weight: 700;
    letter-spacing: -0.5px;
    margin: 2px 0;
  }
  .top-name {
    font-size: 11px;
    color: #555;
    margin-bottom: 8px;
  }
  .top-metrics {
    font-size: 12px;
    display: flex;
    gap: 24px;
    flex-wrap: wrap;
  }
  .top-metric-label {
    font-size: 9px;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    color: #999;
    display: block;
  }
  .badge {
    display: inline-block;
    font-size: 9px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    padding: 2px 6px;
    border: 1px solid #000;
    margin-left: 8px;
    vertical-align: middle;
  }
  .badge-inv { background: #000; color: #fff; border-color: #000; }
  .cta-wrap { margin: 20px 0 12px 0; }
  .cta-btn {
    display: inline-block;
    background: #000;
    color: #fff;
    font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1px;
    padding: 10px 22px;
    text-decoration: none;
    border: none;
  }
  .cta-btn:hover { background: #333; }
  .cta-hint { font-size: 10px; color: #999; margin-top: 8px; line-height: 1.5; }
  .exclu { color: #999; }
  .footer {
    margin-top: 40px;
    padding-top: 12px;
    border-top: 1px solid #000;
    font-size: 10px;
    color: #999;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
  @media (max-width: 600px) {
    body { padding: 20px 16px; }
    .top-metrics { flex-direction: column; gap: 8px; }
  }
"""


# ──────────────────────────────────────────────────────────────────────────────
# Rapport hebdomadaire
# ──────────────────────────────────────────────────────────────────────────────

def generate_weekly_report(
    ranked: pd.DataFrame,
    top_n: list[dict],
    current_allocation: list[dict],
    spy_ret_1m: float | None,
    run_date: date | None = None,
    confirm_url: str | None = None,
) -> str:
    run_date = run_date or date.today()

    # ── Portfolio Allocation : comparaison actuel vs cible ────────────────────
    if not top_n:
        perf_section = """
        <div class="signal">
          <div class="signal-title">Aucun ETF éligible</div>
          <div class="signal-body">Tous les ETFs sont sous leur MM200j. Rester en cash.</div>
        </div>"""
    else:
        current_tickers = {h["ticker"] for h in current_allocation}
        target_tickers  = {e["ticker"] for e in top_n[:2]}
        needs_rebalance = current_tickers != target_tickers

        target_by_ticker = {e["ticker"]: e for e in top_n[:2]}

        # Union actuel + cible, cible en premier
        all_tickers_ordered = list(target_tickers) + [
            t for t in current_tickers if t not in target_tickers
        ]

        rows = ""
        for ticker in all_tickers_ordered:
            in_current = ticker in current_tickers
            in_target  = ticker in target_tickers

            row_data = ranked[ranked["ticker"] == ticker]
            ret_3m = float(row_data["ret_3m"].iloc[0]) if not row_data.empty else None
            score  = float(row_data["score"].iloc[0])  if not row_data.empty else None
            name   = row_data["name"].iloc[0]           if not row_data.empty else ticker

            if in_current and in_target:
                action = '<span style="font-weight:700;">Conserver</span>'
                row_style = ""
            elif in_target and not in_current:
                action = '<span style="font-weight:700;">Acheter</span>'
                row_style = ""
            else:
                action = '<span style="color:#999;">Vendre</span>'
                row_style = ' style="color:#999;"'

            rows += f"""
            <tr>
              <td{row_style}><strong>{_ht(ticker)}</strong></td>
              <td{row_style} style="font-size:11px;{'color:#999;' if not in_target else ''}">{name}</td>
              <td class="num"{row_style}>{"50%" if in_target else "—"}</td>
              <td class="num" style="{_weight(ret_3m) if in_target else 'color:#999;'}">{_pct(ret_3m)}</td>
              <td class="num" style="{_weight(score) if in_target else 'color:#999;'}">{_pct(score)}</td>
              <td style="font-size:11px;">{action}</td>
            </tr>"""

        # SPY benchmark
        rows += f"""
        <tr>
          <td style="color:#999;"><strong>SPY</strong></td>
          <td style="color:#999;font-size:11px;">S&amp;P 500</td>
          <td class="num" style="color:#999;">—</td>
          <td class="num" style="{_weight(spy_ret_1m)}color:#999;">{_pct(spy_ret_1m)}</td>
          <td class="num" style="color:#999;">—</td>
          <td style="color:#999;font-size:11px;">Benchmark</td>
        </tr>"""

        # Signal
        if not current_allocation:
            signal_html = f"""
            <div class="signal invert">
              <div class="signal-title">Initialisation</div>
              <div class="signal-body">Aucune allocation actuelle — investir 50% Top 1 / 50% Top 2.</div>
            </div>
            {_cta_button(confirm_url)}"""
        elif needs_rebalance:
            added   = sorted(target_tickers - current_tickers)
            removed = sorted(current_tickers - target_tickers)
            parts   = []
            if added:   parts.append(f"Acheter {', '.join(added)}")
            if removed: parts.append(f"Vendre {', '.join(removed)}")
            signal_html = f"""
            <div class="signal invert">
              <div class="signal-title">Rebalancement suggéré</div>
              <div class="signal-body">{' &nbsp;·&nbsp; '.join(parts)}</div>
            </div>
            {_cta_button(confirm_url)}"""
        else:
            signal_html = """
            <div class="signal">
              <div class="signal-title">Allocation conforme</div>
              <div class="signal-body">Aucun changement nécessaire.</div>
            </div>"""

        perf_section = f"""
        <div class="section">
          <div class="section-label">Portfolio Allocation</div>
          {signal_html}
          <table>
            <thead><tr>
              <th>Ticker</th><th>Nom</th>
              <th class="num">Poids cible</th>
              <th class="num">Perf M3</th>
              <th class="num">Score</th>
              <th>Action</th>
            </tr></thead>
            <tbody>{rows}</tbody>
          </table>
        </div>"""

    # ── Classement ────────────────────────────────────────────────────────────
    ranking_rows = ""
    for _, row in ranked.iterrows():
        eligible = row["status"] == "✓"
        rank_str = f"{int(row['rank'])}" if pd.notna(row.get("rank")) else "—"
        style = ' class="exclu"' if not eligible else ""
        status_cell = "" if eligible else f'<span style="font-size:10px;color:#999;">{row["status"]}</span>'

        ranking_rows += f"""
        <tr{style}>
          <td class="num" style="color:#999;font-size:11px;">{rank_str}</td>
          <td><strong>{_ht(row['ticker'])}</strong></td>
          <td style="color:#555;font-size:11px;">{row['name']}</td>
          <td>{row['sector']}</td>
          <td style="color:#999;">{row['region']}</td>
          <td class="num" style="{_weight(row['ret_3m'])}">{_pct(row['ret_3m'])}</td>
          <td class="num" style="{_weight(row['ret_6m'])}">{_pct(row['ret_6m'])}</td>
          <td class="num" style="{_weight(row['score'])}font-size:13px;">{_pct(row['score'])}</td>
          <td style="font-size:10px;color:#999;">{status_cell}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Nisabā — {run_date.strftime('%d/%m/%Y')}</title>
  <style>{_BASE_CSS}</style>
</head>
<body>
  <div class="masthead">
    <div class="masthead-title">Nisabā</div>
    <div class="masthead-sub">Suivi hebdomadaire &mdash; {run_date.strftime('%d %B %Y')}</div>
  </div>

  {perf_section}

  <div class="section">
    <div class="section-label">Momentum — 21 ETFs</div>
    <table>
      <thead><tr>
        <th class="num">#</th>
        <th>Ticker</th><th>Nom</th><th>Secteur</th><th>Zone</th>
        <th class="num">M3-skip</th>
        <th class="num">M6-skip</th>
        <th class="num">Score</th>
        <th>Statut</th>
      </tr></thead>
      <tbody>{ranking_rows}</tbody>
    </table>
  </div>

  <div class="footer">
    Nisabā &mdash; {run_date.strftime('%d/%m/%Y')} &mdash; Score = 50% M3-skip + 50% M6-skip &mdash; Filtre MM200j
  </div>
</body>
</html>"""


# ──────────────────────────────────────────────────────────────────────────────
# Rapport mensuel
# ──────────────────────────────────────────────────────────────────────────────

def generate_monthly_report(
    ranked: pd.DataFrame,
    top_n: list[dict],
    current_allocation: list[dict],
    run_date: date | None = None,
    confirm_url: str | None = None,
) -> str:
    run_date = run_date or date.today()
    current_tickers = {h["ticker"] for h in current_allocation}
    new_tickers = {e["ticker"] for e in top_n[:2]}

    # ── Signal ────────────────────────────────────────────────────────────────
    if not current_allocation:
        signal_html = f"""
        <div class="signal invert" style="margin-bottom:8px;">
          <div class="signal-title">Initialisation</div>
          <div class="signal-body">Aucune allocation actuelle. Investir 50% Top 1 / 50% Top 2.</div>
        </div>
        {_cta_button(confirm_url)}"""
    elif current_tickers != new_tickers:
        added = new_tickers - current_tickers
        removed = current_tickers - new_tickers
        lines = []
        if added:   lines.append(f"Acheter : <strong>{', '.join(sorted(added))}</strong>")
        if removed: lines.append(f"Vendre : <strong>{', '.join(sorted(removed))}</strong>")
        signal_html = f"""
        <div class="signal invert" style="margin-bottom:8px;">
          <div class="signal-title">Rebalancer</div>
          <div class="signal-body">{'&nbsp;&nbsp;·&nbsp;&nbsp;'.join(lines)}</div>
        </div>
        {_cta_button(confirm_url)}"""
    else:
        signal_html = """
        <div class="signal">
          <div class="signal-title">Conserver</div>
          <div class="signal-body">Aucun changement — le Top 2 est identique au mois précédent.</div>
        </div>"""

    # ── Top 2 ─────────────────────────────────────────────────────────────────
    top2_html = ""
    for i, etf in enumerate(top_n[:2], 1):
        is_new = etf["ticker"] not in current_tickers
        badge = '<span class="badge badge-inv">Nouveau</span>' if is_new else '<span class="badge">Reconduit</span>'
        top2_html += f"""
        <div class="top-block">
          <div class="top-rank">Top {i} &mdash; 50%</div>
          <div class="top-ticker">{_ht(etf['ticker'])}{badge}</div>
          <div class="top-name">{etf['name']}</div>
          <div class="top-metrics">
            <div>
              <span class="top-metric-label">Score</span>
              <strong>{_pct(etf['score'])}</strong>
            </div>
            <div>
              <span class="top-metric-label">M3-skip</span>
              {_pct(etf['ret_3m'])}
            </div>
            <div>
              <span class="top-metric-label">M6-skip</span>
              {_pct(etf['ret_6m'])}
            </div>
          </div>
        </div>"""

    if not top_n:
        top2_html = """
        <div class="signal">
          <div class="signal-title">Aucun ETF éligible</div>
          <div class="signal-body">Tous les ETFs sont sous leur MM200j. Rester en cash.</div>
        </div>"""

    # ── Classement ────────────────────────────────────────────────────────────
    ranking_rows = ""
    for _, row in ranked.iterrows():
        eligible = row["status"] == "✓"
        rank_str = f"{int(row['rank'])}" if pd.notna(row.get("rank")) else "—"
        style = ' class="exclu"' if not eligible else ""
        status_cell = "" if eligible else f'<span style="font-size:10px;color:#999;">{row["status"]}</span>'

        ranking_rows += f"""
        <tr{style}>
          <td class="num" style="color:#999;font-size:11px;">{rank_str}</td>
          <td><strong>{_ht(row['ticker'])}</strong></td>
          <td style="color:#555;font-size:11px;">{row['name']}</td>
          <td>{row['sector']}</td>
          <td style="color:#999;">{row['region']}</td>
          <td class="num" style="{_weight(row['ret_3m'])}">{_pct(row['ret_3m'])}</td>
          <td class="num" style="{_weight(row['ret_6m'])}">{_pct(row['ret_6m'])}</td>
          <td class="num" style="{_weight(row['score'])}font-size:13px;">{_pct(row['score'])}</td>
          <td style="font-size:10px;color:#999;">{status_cell}</td>
        </tr>"""

    month_fr = {
        1: "Janvier", 2: "Février", 3: "Mars", 4: "Avril",
        5: "Mai", 6: "Juin", 7: "Juillet", 8: "Août",
        9: "Septembre", 10: "Octobre", 11: "Novembre", 12: "Décembre"
    }[run_date.month]

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Nisabā — {month_fr} {run_date.year}</title>
  <style>{_BASE_CSS}</style>
</head>
<body>
  <div class="masthead">
    <div class="masthead-title">Nisabā</div>
    <div class="masthead-sub">Rebalancement &mdash; {month_fr} {run_date.year}</div>
  </div>

  {signal_html}

  <div class="section">
    <div class="section-label">Allocation cible</div>
    {top2_html}
  </div>

  <div class="section">
    <div class="section-label">Momentum — 21 ETFs</div>
    <table>
      <thead><tr>
        <th class="num">#</th>
        <th>Ticker</th><th>Nom</th><th>Secteur</th><th>Zone</th>
        <th class="num">M3-skip</th>
        <th class="num">M6-skip</th>
        <th class="num">Score</th>
        <th>Statut</th>
      </tr></thead>
      <tbody>{ranking_rows}</tbody>
    </table>
  </div>

  <div class="footer">
    Nisabā &mdash; {run_date.strftime('%d/%m/%Y')} &mdash; Score = 50% M3-skip + 50% M6-skip &mdash; Filtre MM200j
  </div>
</body>
</html>"""
