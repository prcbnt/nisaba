"""
report_generator.py — Génération des emails HTML (hebdomadaire et mensuel).

Design : sobre, lisible sur mobile (responsive), pas de dépendances externes.
"""

from datetime import date

import numpy as np
import pandas as pd

# ──────────────────────────────────────────────────────────────────────────────
# Helpers de formatage
# ──────────────────────────────────────────────────────────────────────────────

def _pct(value, decimals: int = 1) -> str:
    """Formate une valeur décimale en pourcentage avec signe."""
    try:
        if value is None or (isinstance(value, float) and np.isnan(value)):
            return "—"
        sign = "+" if value >= 0 else ""
        return f"{sign}{value * 100:.{decimals}f}%"
    except Exception:
        return "—"


def _color(value) -> str:
    """Vert si positif, rouge si négatif, gris si absent."""
    try:
        if value is None or (isinstance(value, float) and np.isnan(value)):
            return "#888"
        return "#27ae60" if value >= 0 else "#e74c3c"
    except Exception:
        return "#888"


# CSS partagé entre les deux templates
_BASE_CSS = """
  * { box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
    max-width: 820px;
    margin: 0 auto;
    padding: 16px;
    color: #2c3e50;
    background: #f4f6f8;
    font-size: 14px;
  }
  .card {
    background: #fff;
    border-radius: 10px;
    box-shadow: 0 1px 6px rgba(0,0,0,.08);
    margin: 16px 0;
    overflow: hidden;
  }
  .card-header {
    padding: 14px 20px;
    font-weight: 700;
    font-size: 15px;
    background: #2c3e50;
    color: white;
  }
  table {
    width: 100%;
    border-collapse: collapse;
  }
  th {
    background: #34495e;
    color: #fff;
    padding: 9px 12px;
    text-align: left;
    font-size: 12px;
    white-space: nowrap;
  }
  td {
    padding: 8px 12px;
    border-bottom: 1px solid #ecf0f1;
    font-size: 13px;
  }
  tr:last-child td { border-bottom: none; }
  tr:hover { background: #f8f9fa; }
  .badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
  }
  .badge-green { background: #d5f5e3; color: #1e8449; }
  .badge-red   { background: #fde8e8; color: #c0392b; }
  .badge-blue  { background: #d6eaf8; color: #1a5276; }
  .badge-gray  { background: #ecf0f1; color: #7f8c8d; }
  .signal-box {
    padding: 16px 20px;
    border-radius: 10px;
    margin: 16px 0;
    font-size: 15px;
    font-weight: 600;
  }
  .signal-green  { background: #d5f5e3; border-left: 5px solid #27ae60; color: #1e8449; }
  .signal-red    { background: #fde8e8; border-left: 5px solid #e74c3c; color: #c0392b; }
  .signal-blue   { background: #d6eaf8; border-left: 5px solid #3498db; color: #1a5276; }
  .top-card {
    padding: 16px 20px;
    border-radius: 10px;
    border: 1px solid #dce1e7;
    margin: 10px 0;
    background: #fff;
  }
  .footer {
    margin-top: 24px;
    font-size: 11px;
    color: #aaa;
    text-align: center;
    padding-top: 12px;
    border-top: 1px solid #dce1e7;
  }
  @media (max-width: 600px) {
    body { padding: 8px; font-size: 13px; }
    td, th { padding: 6px 8px; font-size: 11px; }
    .card-header { font-size: 13px; }
    .overflow-x { overflow-x: auto; }
  }
"""


# ──────────────────────────────────────────────────────────────────────────────
# Rapport hebdomadaire
# ──────────────────────────────────────────────────────────────────────────────

def generate_weekly_report(
    ranked: pd.DataFrame,
    weekly_perf: dict,
    spy_ret_1w: float | None,
    run_date: date | None = None,
) -> str:
    """
    Génère l'email HTML hebdomadaire contenant :
    - Performance 7j du portefeuille vs SPY
    - Classement momentum complet des 21 ETFs
    """
    run_date = run_date or date.today()

    # ── Tableau performance portefeuille ──────────────────────────────────────
    if weekly_perf:
        perf_rows = ""
        for ticker, data in weekly_perf.items():
            ret = data.get("ret_1w")
            perf_rows += f"""
            <tr>
              <td><strong>{ticker}</strong></td>
              <td>{data['name']}</td>
              <td style="text-align:center">{int(data['weight'] * 100)}%</td>
              <td style="color:{_color(ret)};font-weight:700;text-align:right">{_pct(ret)}</td>
            </tr>"""

        spy_color = _color(spy_ret_1w)
        perf_rows += f"""
        <tr style="border-top:2px solid #dce1e7;background:#f8f9fa">
          <td><strong>SPY</strong></td>
          <td>S&amp;P 500 (benchmark)</td>
          <td style="text-align:center">—</td>
          <td style="color:{spy_color};font-weight:700;text-align:right">{_pct(spy_ret_1w)}</td>
        </tr>"""

        perf_section = f"""
        <div class="card">
          <div class="card-header">📈 Performance du portefeuille — 7 derniers jours</div>
          <div class="overflow-x">
            <table>
              <thead><tr>
                <th>Ticker</th><th>Nom</th><th style="text-align:center">Poids</th>
                <th style="text-align:right">Perf 7j</th>
              </tr></thead>
              <tbody>{perf_rows}</tbody>
            </table>
          </div>
        </div>"""
    else:
        perf_section = """
        <div class="signal-box signal-blue">
          ℹ️ Aucun portefeuille en cours. Lancez le rapport mensuel pour initialiser l'allocation.
        </div>"""

    # ── Tableau classement momentum ───────────────────────────────────────────
    ranking_rows = ""
    for _, row in ranked.iterrows():
        eligible = row["status"] == "✓"
        rank_str = f"#{int(row['rank'])}" if pd.notna(row.get("rank")) else "—"
        row_style = "opacity:0.55;" if not eligible else ""
        status_badge = (
            '<span class="badge badge-green">✓</span>'
            if eligible
            else f'<span class="badge badge-gray">{row["status"]}</span>'
        )

        ranking_rows += f"""
        <tr style="{row_style}">
          <td style="font-weight:700;text-align:center">{rank_str}</td>
          <td><strong>{row['ticker']}</strong></td>
          <td style="font-size:12px;color:#555">{row['name']}</td>
          <td>{row['sector']}</td>
          <td>{row['region']}</td>
          <td style="color:{_color(row['ret_1m'])};text-align:right">{_pct(row['ret_1m'])}</td>
          <td style="color:{_color(row['ret_3m'])};text-align:right">{_pct(row['ret_3m'])}</td>
          <td style="color:{_color(row['score'])};font-weight:700;text-align:right">{_pct(row['score'])}</td>
          <td style="text-align:center">{status_badge}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Nisabā — Hebdomadaire {run_date.strftime('%d/%m/%Y')}</title>
  <style>{_BASE_CSS}</style>
</head>
<body>
  <h1 style="color:#1a1a2e;border-bottom:3px solid #3498db;padding-bottom:10px;font-size:22px;">
    📊 Nisabā — Suivi hebdomadaire
  </h1>
  <p style="color:#888;margin-top:-8px;">Semaine du {run_date.strftime('%d %B %Y')}</p>

  {perf_section}

  <div class="card">
    <div class="card-header">🏆 Classement Momentum — 21 ETFs</div>
    <div class="overflow-x">
      <table>
        <thead><tr>
          <th style="text-align:center">Rang</th>
          <th>Ticker</th><th>Nom</th><th>Secteur</th><th>Zone</th>
          <th style="text-align:right">M1</th>
          <th style="text-align:right">M3</th>
          <th style="text-align:right">Score</th>
          <th style="text-align:center">Statut</th>
        </tr></thead>
        <tbody>{ranking_rows}</tbody>
      </table>
    </div>
  </div>

  <div class="footer">
    Généré le {run_date.strftime('%d/%m/%Y')} · Score = 50% M1 + 50% M3 · Filtre : cours &gt; MM200j
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
) -> str:
    """
    Génère l'email HTML mensuel contenant :
    - Signal REBALANCER / CONSERVER / INITIALISER
    - Top 1 et Top 2 avec détail du score
    - Classement complet des 21 ETFs
    """
    run_date = run_date or date.today()
    current_tickers = {h["ticker"] for h in current_allocation}
    new_tickers = {e["ticker"] for e in top_n[:2]}

    # ── Signal de décision ────────────────────────────────────────────────────
    if not current_allocation:
        signal_html = """
        <div class="signal-box signal-blue">
          🚀 <strong>INITIALISATION</strong> — Aucune allocation actuelle.<br>
          Investir 50% sur le Top 1 et 50% sur le Top 2 ci-dessous.
        </div>"""
    elif current_tickers != new_tickers:
        added = new_tickers - current_tickers
        removed = current_tickers - new_tickers
        lines = []
        if added:
            lines.append(f"Acheter : <strong>{', '.join(added)}</strong>")
        if removed:
            lines.append(f"Vendre : <strong>{', '.join(removed)}</strong>")
        signal_html = f"""
        <div class="signal-box signal-red">
          🔄 <strong>REBALANCER</strong><br>
          {'<br>'.join(lines)}
        </div>"""
    else:
        signal_html = """
        <div class="signal-box signal-green">
          ✅ <strong>CONSERVER</strong> — Aucun changement nécessaire.<br>
          Le Top 2 est identique au mois précédent.
        </div>"""

    # ── Top 2 cards ───────────────────────────────────────────────────────────
    top2_html = ""
    for i, etf in enumerate(top_n[:2], 1):
        is_new = etf["ticker"] not in current_tickers
        new_badge = (
            ' <span class="badge badge-red">Nouveau</span>' if is_new else
            ' <span class="badge badge-green">Reconduit</span>'
        )
        top2_html += f"""
        <div class="top-card">
          <div style="font-size:18px;font-weight:800;color:#1a1a2e;">
            Top {i} : {etf['ticker']}{new_badge}
          </div>
          <div style="color:#555;margin:4px 0 8px;">{etf['name']}</div>
          <div style="font-size:13px;">
            Score : <strong style="color:{_color(etf['score'])}">{_pct(etf['score'])}</strong>
            &nbsp;·&nbsp; M1 : <span style="color:{_color(etf['ret_1m'])}">{_pct(etf['ret_1m'])}</span>
            &nbsp;·&nbsp; M3 : <span style="color:{_color(etf['ret_3m'])}">{_pct(etf['ret_3m'])}</span>
          </div>
          <div style="margin-top:10px;color:#3498db;font-weight:700;">→ Allocation cible : 50%</div>
        </div>"""

    if not top_n:
        top2_html = """
        <div class="signal-box signal-red">
          ⚠️ Aucun ETF éligible (tous sous MM200j). Rester en cash ou conserver les positions.
        </div>"""

    # ── Tableau classement ────────────────────────────────────────────────────
    ranking_rows = ""
    for _, row in ranked.iterrows():
        eligible = row["status"] == "✓"
        rank_str = f"#{int(row['rank'])}" if pd.notna(row.get("rank")) else "—"
        row_style = "opacity:0.55;" if not eligible else ""
        status_badge = (
            '<span class="badge badge-green">✓</span>'
            if eligible
            else f'<span class="badge badge-gray">{row["status"]}</span>'
        )

        ranking_rows += f"""
        <tr style="{row_style}">
          <td style="font-weight:700;text-align:center">{rank_str}</td>
          <td><strong>{row['ticker']}</strong></td>
          <td style="font-size:12px;color:#555">{row['name']}</td>
          <td>{row['sector']}</td>
          <td>{row['region']}</td>
          <td style="color:{_color(row['ret_1m'])};text-align:right">{_pct(row['ret_1m'])}</td>
          <td style="color:{_color(row['ret_3m'])};text-align:right">{_pct(row['ret_3m'])}</td>
          <td style="color:{_color(row['score'])};font-weight:700;text-align:right">{_pct(row['score'])}</td>
          <td style="text-align:center">{status_badge}</td>
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
  <title>Nisabā — Rebalancement {month_fr} {run_date.year}</title>
  <style>{_BASE_CSS}</style>
</head>
<body>
  <h1 style="color:#1a1a2e;border-bottom:3px solid #e67e22;padding-bottom:10px;font-size:22px;">
    📅 Nisabā — Rebalancement {month_fr} {run_date.year}
  </h1>

  {signal_html}

  <h2 style="font-size:16px;color:#2c3e50;margin-top:24px;">Allocation cible</h2>
  {top2_html}

  <div class="card" style="margin-top:24px;">
    <div class="card-header">🏆 Classement Momentum complet — 21 ETFs</div>
    <div class="overflow-x">
      <table>
        <thead><tr>
          <th style="text-align:center">Rang</th>
          <th>Ticker</th><th>Nom</th><th>Secteur</th><th>Zone</th>
          <th style="text-align:right">M1</th>
          <th style="text-align:right">M3</th>
          <th style="text-align:right">Score</th>
          <th style="text-align:center">Statut</th>
        </tr></thead>
        <tbody>{ranking_rows}</tbody>
      </table>
    </div>
  </div>

  <div class="footer">
    Généré le {run_date.strftime('%d/%m/%Y')} · Score = 50% M1 + 50% M3 · Filtre : cours &gt; MM200j
  </div>
</body>
</html>"""
