"""
report_generator.py — Génération des emails HTML (hebdomadaire et mensuel).

Design : Swiss / International Typographic Style.
         Helvetica, noir et blanc, grille stricte, typographie forte.

Structure email :
  Masthead
  ├─ Stratégie Macro (signal + allocation + classement 21 ETFs)
  └─ Stratégie Thématique (signal + allocation + classement 10 ETFs)
  CTA button unique (si rebalancement à faire dans l'une ou l'autre stratégie)
  Footer
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
  .strategy-header {
    font-size: 13px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    color: #000;
    border-top: 2px solid #000;
    padding-top: 12px;
    margin-top: 44px;
    margin-bottom: 20px;
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
  .cta-wrap { margin: 28px 0 12px 0; }
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
# Tableaux récapitulatifs (en tête d'email)
# ──────────────────────────────────────────────────────────────────────────────

def _summary_weekly(
    strategies: list[dict],   # [{label, portfolio_weight, top_n, current, perf_1w}]
    spy_ret_1w: float | None,
    ief_ret_1w: float | None,
) -> str:
    """Tableau récapitulatif hebdomadaire : une ligne par stratégie + benchmarks."""
    rows = ""
    for s in strategies:
        current_tickers = {h["ticker"] for h in s["current"]}
        target_tickers  = {e["ticker"] for e in s["top_n"][:2]}
        needs_rb        = current_tickers != target_tickers
        needs_init      = not s["current"] and bool(s["top_n"])
        if needs_init:
            action_html = '<span style="font-weight:700;">Initialiser</span>'
        elif needs_rb:
            action_html = '<span style="font-weight:700;">Rebalancer</span>'
        else:
            action_html = '<span style="color:#999;">Conserver</span>'

        holdings = ", ".join(_ht(t) for t in current_tickers) if current_tickers else "—"

        # Perf 1S pondérée du portefeuille (holdings actuels)
        perf_1w = None
        if s.get("perf_1w"):
            total = sum(
                (v.get("ret_1w") or 0) * v.get("weight", 0.5)
                for v in s["perf_1w"].values()
                if v.get("ret_1w") is not None
            )
            if any(v.get("ret_1w") is not None for v in s["perf_1w"].values()):
                perf_1w = total

        weight_pct = f"{int(s['portfolio_weight'] * 100)}%"
        rows += f"""
        <tr>
          <td style="font-weight:700;">{s['label']}</td>
          <td class="num">{weight_pct}</td>
          <td style="font-size:11px;color:#555;">{holdings}</td>
          <td class="num" style="{_weight(perf_1w)}">{_pct(perf_1w)}</td>
          <td style="font-size:11px;">{action_html}</td>
        </tr>"""

    # Lignes benchmark
    rows += f"""
        <tr style="border-top:1px solid #ccc;">
          <td style="color:#999;">SPY</td>
          <td class="num" style="color:#999;font-size:10px;">Réf.</td>
          <td style="color:#999;font-size:11px;">S&amp;P 500</td>
          <td class="num" style="{_weight(spy_ret_1w)}color:#999;">{_pct(spy_ret_1w)}</td>
          <td style="color:#999;font-size:10px;">Benchmark</td>
        </tr>
        <tr>
          <td style="color:#999;">IEF</td>
          <td class="num" style="color:#999;font-size:10px;">Réf.</td>
          <td style="color:#999;font-size:11px;">US Treasuries 7-10 ans</td>
          <td class="num" style="{_weight(ief_ret_1w)}color:#999;">{_pct(ief_ret_1w)}</td>
          <td style="color:#999;font-size:10px;">Benchmark</td>
        </tr>"""

    return f"""
    <div class="section" style="margin-bottom:44px;">
      <div class="section-label">Résumé du portefeuille</div>
      <table>
        <thead><tr>
          <th>Stratégie</th>
          <th class="num">Poids</th>
          <th>Holdings</th>
          <th class="num">Perf 1S</th>
          <th>Action</th>
        </tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </div>"""


def _summary_monthly(
    strategies: list[dict],   # [{label, portfolio_weight, top_n, current}]
    spy_ret_1m: float | None,
    ief_ret_1m: float | None,
) -> str:
    """Tableau récapitulatif mensuel : une ligne par stratégie + benchmarks 1M."""
    rows = ""
    for s in strategies:
        current_tickers = {h["ticker"] for h in s["current"]}
        target_tickers  = {e["ticker"] for e in s["top_n"][:2]}
        needs_rb        = current_tickers != target_tickers
        needs_init      = not s["current"] and bool(s["top_n"])
        if needs_init:
            action_html = '<span style="font-weight:700;">Initialiser</span>'
        elif needs_rb:
            action_html = '<span style="font-weight:700;">Rebalancer</span>'
        else:
            action_html = '<span style="color:#999;">Conserver</span>'

        current_str = ", ".join(_ht(t) for t in current_tickers) if current_tickers else "—"
        target_str  = ", ".join(_ht(e["ticker"]) for e in s["top_n"][:2]) if s["top_n"] else "—"
        weight_pct  = f"{int(s['portfolio_weight'] * 100)}%"

        rows += f"""
        <tr>
          <td style="font-weight:700;">{s['label']}</td>
          <td class="num">{weight_pct}</td>
          <td style="color:#999;font-size:11px;">{current_str}</td>
          <td style="color:#999;font-size:11px;padding:0 4px;">→</td>
          <td style="font-size:11px;font-weight:700;">{target_str}</td>
          <td style="font-size:11px;">{action_html}</td>
        </tr>"""

    rows += f"""
        <tr style="border-top:1px solid #ccc;">
          <td style="color:#999;">SPY</td>
          <td class="num" style="color:#999;font-size:10px;">Réf.</td>
          <td colspan="2" style="color:#999;font-size:11px;">S&amp;P 500</td>
          <td class="num" style="{_weight(spy_ret_1m)}color:#999;">{_pct(spy_ret_1m)}</td>
          <td style="color:#999;font-size:10px;">1M</td>
        </tr>
        <tr>
          <td style="color:#999;">IEF</td>
          <td class="num" style="color:#999;font-size:10px;">Réf.</td>
          <td colspan="2" style="color:#999;font-size:11px;">US Treasuries 7-10 ans</td>
          <td class="num" style="{_weight(ief_ret_1m)}color:#999;">{_pct(ief_ret_1m)}</td>
          <td style="color:#999;font-size:10px;">1M</td>
        </tr>"""

    return f"""
    <div class="section" style="margin-bottom:44px;">
      <div class="section-label">Résumé du rebalancement</div>
      <table>
        <thead><tr>
          <th>Stratégie</th>
          <th class="num">Poids</th>
          <th>Actuel</th>
          <th></th>
          <th>Cible</th>
          <th>Action</th>
        </tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </div>"""


# ──────────────────────────────────────────────────────────────────────────────
# Blocs de rendu par stratégie (privés)
# ──────────────────────────────────────────────────────────────────────────────

def _weekly_strategy_block(
    ranked: pd.DataFrame,
    top_n: list[dict],
    current: list[dict],
    alloc_col_label: str,
    alloc_col_key: str,
    rank_col1_label: str,
    rank_col1_key: str,
    rank_col2_label: str,
    rank_col2_key: str,
    ma_label: str,
    extra_rows: str = "",
) -> tuple[str, bool]:
    """
    Génère le contenu hebdomadaire d'une stratégie (sans l'en-tête stratégie).
    Retourne (html, needs_action) où needs_action = True si un rebalancement
    ou une initialisation est nécessaire.
    """
    current_tickers = {h["ticker"] for h in current}
    target_tickers  = {e["ticker"] for e in top_n[:2]}
    needs_rb     = (current_tickers != target_tickers) if top_n else False
    needs_action = needs_rb or (not current and bool(top_n))
    is_defensive = bool(top_n) and top_n[0].get("_defensive", False)

    # ── Signal ────────────────────────────────────────────────────────────────
    if is_defensive:
        if top_n[0]["ticker"] in current_tickers and not needs_rb:
            signal_html = f"""
        <div class="signal">
          <div class="signal-title">Position défensive — IEF maintenu</div>
          <div class="signal-body">Aucun ETF > {ma_label}. Conserver IEF (obligations 7-10 ans US).</div>
        </div>"""
        else:
            signal_html = f"""
        <div class="signal invert">
          <div class="signal-title">Position défensive — IEF</div>
          <div class="signal-body">Aucun ETF de l'univers ne passe le filtre {ma_label}. Allouer 100% vers IEF (obligations 7-10 ans US).</div>
        </div>"""
    elif not top_n:
        signal_html = f"""
        <div class="signal">
          <div class="signal-title">Aucun ETF éligible</div>
          <div class="signal-body">Tous les ETFs sont sous leur {ma_label}. Rester en cash.</div>
        </div>"""
    elif not current:
        signal_html = """
        <div class="signal invert">
          <div class="signal-title">Initialisation</div>
          <div class="signal-body">Aucune allocation actuelle — investir 50% Top 1 / 50% Top 2.</div>
        </div>"""
    elif needs_rb:
        added   = sorted(target_tickers - current_tickers)
        removed = sorted(current_tickers - target_tickers)
        parts   = []
        if added:   parts.append(f"Acheter {', '.join(added)}")
        if removed: parts.append(f"Vendre {', '.join(removed)}")
        signal_html = f"""
        <div class="signal invert">
          <div class="signal-title">Rebalancement suggéré</div>
          <div class="signal-body">{' &nbsp;·&nbsp; '.join(parts)}</div>
        </div>"""
    else:
        signal_html = """
        <div class="signal">
          <div class="signal-title">Allocation conforme</div>
          <div class="signal-body">Aucun changement nécessaire.</div>
        </div>"""

    # ── Allocation table ───────────────────────────────────────────────────────
    if not top_n:
        alloc_section = signal_html
    else:
        all_tickers_ordered = list(target_tickers) + [
            t for t in current_tickers if t not in target_tickers
        ]
        top_n_by_ticker = {e["ticker"]: e for e in top_n}
        n_target = len(target_tickers)
        weight_pct = f"{100 // n_target}%" if n_target > 0 else "—"
        rows = ""
        for ticker in all_tickers_ordered:
            in_current = ticker in current_tickers
            in_target  = ticker in target_tickers

            row_data = ranked[ranked["ticker"] == ticker]
            col1_val = (
                float(row_data[alloc_col_key].iloc[0])
                if not row_data.empty and alloc_col_key in row_data.columns
                else None
            )
            score = float(row_data["score"].iloc[0]) if not row_data.empty else None
            name  = (
                row_data["name"].iloc[0] if not row_data.empty
                else top_n_by_ticker.get(ticker, {}).get("name", ticker)
            )

            if in_current and in_target:
                action    = '<span style="font-weight:700;">Conserver</span>'
                row_style = ""
            elif in_target:
                action    = '<span style="font-weight:700;">Acheter</span>'
                row_style = ""
            else:
                action    = '<span style="color:#999;">Vendre</span>'
                row_style = ' style="color:#999;"'

            rows += f"""
            <tr>
              <td{row_style}><strong>{_ht(ticker)}</strong></td>
              <td{row_style} style="font-size:11px;{'color:#999;' if not in_target else ''}">{name}</td>
              <td class="num"{row_style}>{weight_pct if in_target else "—"}</td>
              <td class="num" style="{_weight(col1_val) if in_target else 'color:#999;'}">{_pct(col1_val)}</td>
              <td class="num" style="{_weight(score) if in_target else 'color:#999;'}">{_pct(score)}</td>
              <td style="font-size:11px;">{action}</td>
            </tr>"""

        rows += extra_rows

        alloc_section = f"""
        <div class="section">
          <div class="section-label">Portfolio Allocation</div>
          {signal_html}
          <table>
            <thead><tr>
              <th>Ticker</th><th>Nom</th>
              <th class="num">Poids cible</th>
              <th class="num">{alloc_col_label}</th>
              <th class="num">Score</th>
              <th>Action</th>
            </tr></thead>
            <tbody>{rows}</tbody>
          </table>
        </div>"""

    # ── Ranking table ─────────────────────────────────────────────────────────
    ranking_rows = ""
    for _, row in ranked.iterrows():
        eligible    = row["status"] == "✓"
        rank_str    = f"{int(row['rank'])}" if pd.notna(row.get("rank")) else "—"
        style       = ' class="exclu"' if not eligible else ""
        status_cell = (
            "" if eligible
            else f'<span style="font-size:10px;color:#999;">{row["status"]}</span>'
        )
        col1_v = row.get(rank_col1_key, np.nan)
        col2_v = row.get(rank_col2_key, np.nan)

        ranking_rows += f"""
        <tr{style}>
          <td class="num" style="color:#999;font-size:11px;">{rank_str}</td>
          <td><strong>{_ht(row['ticker'])}</strong></td>
          <td style="color:#555;font-size:11px;">{row['name']}</td>
          <td>{row['sector']}</td>
          <td style="color:#999;">{row['region']}</td>
          <td class="num" style="{_weight(col1_v)}">{_pct(col1_v)}</td>
          <td class="num" style="{_weight(col2_v)}">{_pct(col2_v)}</td>
          <td class="num" style="{_weight(row['score'])}font-size:13px;">{_pct(row['score'])}</td>
          <td style="font-size:10px;color:#999;">{status_cell}</td>
        </tr>"""

    html = f"""
    {alloc_section}
    <div class="section">
      <div class="section-label">Classement Momentum</div>
      <table>
        <thead><tr>
          <th class="num">#</th>
          <th>Ticker</th><th>Nom</th><th>Secteur</th><th>Zone</th>
          <th class="num">{rank_col1_label}</th>
          <th class="num">{rank_col2_label}</th>
          <th class="num">Score</th>
          <th>Statut</th>
        </tr></thead>
        <tbody>{ranking_rows}</tbody>
      </table>
    </div>"""

    return html, needs_action


def _monthly_strategy_block(
    ranked: pd.DataFrame,
    top_n: list[dict],
    current: list[dict],
    top2_m1_label: str,
    top2_m1_key: str,
    top2_m2_label: str,
    top2_m2_key: str,
    rank_col1_label: str,
    rank_col1_key: str,
    rank_col2_label: str,
    rank_col2_key: str,
    ma_label: str,
) -> tuple[str, bool]:
    """
    Génère le contenu mensuel d'une stratégie (sans l'en-tête stratégie).
    Retourne (html, needs_action).
    """
    current_tickers = {h["ticker"] for h in current}
    new_tickers     = {e["ticker"] for e in top_n[:2]}
    needs_rb        = current_tickers != new_tickers
    needs_action    = needs_rb or (not current and bool(top_n))
    is_defensive    = bool(top_n) and top_n[0].get("_defensive", False)

    # ── Signal ────────────────────────────────────────────────────────────────
    if is_defensive:
        if top_n[0]["ticker"] in current_tickers and not needs_rb:
            signal_html = f"""
        <div class="signal">
          <div class="signal-title">Position défensive — IEF maintenu</div>
          <div class="signal-body">Aucun ETF > {ma_label}. Conserver IEF (obligations 7-10 ans US).</div>
        </div>"""
        else:
            signal_html = f"""
        <div class="signal invert" style="margin-bottom:8px;">
          <div class="signal-title">Position défensive — IEF</div>
          <div class="signal-body">Aucun ETF de l'univers ne passe le filtre {ma_label}. Allouer 100% vers IEF (obligations 7-10 ans US).</div>
        </div>"""
    elif not top_n:
        signal_html = f"""
        <div class="signal">
          <div class="signal-title">Aucun ETF éligible</div>
          <div class="signal-body">Tous les ETFs sont sous leur {ma_label}. Rester en cash.</div>
        </div>"""
    elif not current:
        signal_html = """
        <div class="signal invert" style="margin-bottom:8px;">
          <div class="signal-title">Initialisation</div>
          <div class="signal-body">Aucune allocation actuelle. Investir 50% Top 1 / 50% Top 2.</div>
        </div>"""
    elif needs_rb:
        added   = new_tickers - current_tickers
        removed = current_tickers - new_tickers
        lines   = []
        if added:   lines.append(f"Acheter : <strong>{', '.join(sorted(added))}</strong>")
        if removed: lines.append(f"Vendre : <strong>{', '.join(sorted(removed))}</strong>")
        signal_html = f"""
        <div class="signal invert" style="margin-bottom:8px;">
          <div class="signal-title">Rebalancer</div>
          <div class="signal-body">{'&nbsp;&nbsp;·&nbsp;&nbsp;'.join(lines)}</div>
        </div>"""
    else:
        signal_html = """
        <div class="signal">
          <div class="signal-title">Conserver</div>
          <div class="signal-body">Aucun changement — le Top 2 est identique au mois précédent.</div>
        </div>"""

    # ── Top 2 cards ───────────────────────────────────────────────────────────
    top2_html = ""
    n_top = len(top_n[:2])
    top_weight_pct = f"{100 // n_top}%" if n_top > 0 else "—"
    for i, etf in enumerate(top_n[:2], 1):
        is_new = etf["ticker"] not in current_tickers
        badge  = (
            '<span class="badge badge-inv">Nouveau</span>'
            if is_new
            else '<span class="badge">Reconduit</span>'
        )
        m1_val = etf.get(top2_m1_key)
        m2_val = etf.get(top2_m2_key)
        top2_html += f"""
        <div class="top-block">
          <div class="top-rank">Top {i} &mdash; {top_weight_pct}</div>
          <div class="top-ticker">{_ht(etf['ticker'])}{badge}</div>
          <div class="top-name">{etf['name']}</div>
          <div class="top-metrics">
            <div>
              <span class="top-metric-label">Score</span>
              <strong>{_pct(etf.get('score'))}</strong>
            </div>
            <div>
              <span class="top-metric-label">{top2_m1_label}</span>
              {_pct(m1_val)}
            </div>
            <div>
              <span class="top-metric-label">{top2_m2_label}</span>
              {_pct(m2_val)}
            </div>
          </div>
        </div>"""

    allocation_section = ""
    if top2_html:
        allocation_section = f"""
        <div class="section">
          <div class="section-label">Allocation cible</div>
          {top2_html}
        </div>"""

    # ── Ranking table ─────────────────────────────────────────────────────────
    ranking_rows = ""
    for _, row in ranked.iterrows():
        eligible    = row["status"] == "✓"
        rank_str    = f"{int(row['rank'])}" if pd.notna(row.get("rank")) else "—"
        style       = ' class="exclu"' if not eligible else ""
        status_cell = (
            "" if eligible
            else f'<span style="font-size:10px;color:#999;">{row["status"]}</span>'
        )
        col1_v = row.get(rank_col1_key, np.nan)
        col2_v = row.get(rank_col2_key, np.nan)

        ranking_rows += f"""
        <tr{style}>
          <td class="num" style="color:#999;font-size:11px;">{rank_str}</td>
          <td><strong>{_ht(row['ticker'])}</strong></td>
          <td style="color:#555;font-size:11px;">{row['name']}</td>
          <td>{row['sector']}</td>
          <td style="color:#999;">{row['region']}</td>
          <td class="num" style="{_weight(col1_v)}">{_pct(col1_v)}</td>
          <td class="num" style="{_weight(col2_v)}">{_pct(col2_v)}</td>
          <td class="num" style="{_weight(row['score'])}font-size:13px;">{_pct(row['score'])}</td>
          <td style="font-size:10px;color:#999;">{status_cell}</td>
        </tr>"""

    html = f"""
    {signal_html}
    {allocation_section}
    <div class="section">
      <div class="section-label">Classement Momentum</div>
      <table>
        <thead><tr>
          <th class="num">#</th>
          <th>Ticker</th><th>Nom</th><th>Secteur</th><th>Zone</th>
          <th class="num">{rank_col1_label}</th>
          <th class="num">{rank_col2_label}</th>
          <th class="num">Score</th>
          <th>Statut</th>
        </tr></thead>
        <tbody>{ranking_rows}</tbody>
      </table>
    </div>"""

    return html, needs_action


# ──────────────────────────────────────────────────────────────────────────────
# Rapport hebdomadaire
# ──────────────────────────────────────────────────────────────────────────────

def generate_weekly_report(
    ranked_macro: pd.DataFrame,
    top_n_macro: list[dict],
    current_macro: list[dict],
    perf_macro: dict,
    ranked_thematic: pd.DataFrame,
    top_n_thematic: list[dict],
    current_thematic: list[dict],
    perf_thematic: dict,
    ranked_satellite: pd.DataFrame,
    top_n_satellite: list[dict],
    current_satellite: list[dict],
    perf_satellite: dict,
    spy_ret_1w: float | None,
    ief_ret_1w: float | None,
    portfolio_weights: dict,
    run_date: date | None = None,
    confirm_url: str | None = None,
) -> str:
    run_date = run_date or date.today()

    summary_html = _summary_weekly(
        strategies=[
            {"label": "Macro",      "portfolio_weight": portfolio_weights.get("macro", 0.45),
             "top_n": top_n_macro,     "current": current_macro,     "perf_1w": perf_macro},
            {"label": "Thématique", "portfolio_weight": portfolio_weights.get("thematic", 0.45),
             "top_n": top_n_thematic,  "current": current_thematic,  "perf_1w": perf_thematic},
            {"label": "Satellite",  "portfolio_weight": portfolio_weights.get("satellite", 0.10),
             "top_n": top_n_satellite, "current": current_satellite, "perf_1w": perf_satellite},
        ],
        spy_ret_1w=spy_ret_1w,
        ief_ret_1w=ief_ret_1w,
    )

    macro_content, macro_action = _weekly_strategy_block(
        ranked=ranked_macro,
        top_n=top_n_macro,
        current=current_macro,
        alloc_col_label="M3-skip",
        alloc_col_key="ret_3m",
        rank_col1_label="M3-skip",
        rank_col1_key="ret_3m",
        rank_col2_label="M6-skip",
        rank_col2_key="ret_6m",
        ma_label="MM200j",
    )

    thematic_content, thematic_action = _weekly_strategy_block(
        ranked=ranked_thematic,
        top_n=top_n_thematic,
        current=current_thematic,
        alloc_col_label="M3",
        alloc_col_key="ret_3m",
        rank_col1_label="M1",
        rank_col1_key="ret_1m",
        rank_col2_label="M3",
        rank_col2_key="ret_3m",
        ma_label="MM150j",
    )

    satellite_content, satellite_action = _weekly_strategy_block(
        ranked=ranked_satellite,
        top_n=top_n_satellite,
        current=current_satellite,
        alloc_col_label="M1",
        alloc_col_key="ret_1m",
        rank_col1_label="M1",
        rank_col1_key="ret_1m",
        rank_col2_label="Score",
        rank_col2_key="score",
        ma_label="—",
    )

    any_action = macro_action or thematic_action or satellite_action
    cta_html   = _cta_button(confirm_url) if any_action else ""

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

  {summary_html}

  <div class="strategy-header" style="margin-top:0;">Stratégie Macro &mdash; 21 ETFs</div>
  {macro_content}

  <div class="strategy-header">Stratégie Thématique &mdash; 10 ETFs</div>
  {thematic_content}

  <div class="strategy-header">Satellite &mdash; Managed Futures</div>
  {satellite_content}

  {cta_html}

  <div class="footer">
    Nisabā &mdash; {run_date.strftime('%d/%m/%Y')} &mdash;
    Macro (45%) : 50% M3-skip + 50% M6-skip · MM200j &mdash;
    Thématique (45%) : 60% M1 + 40% M3 · MM150j &mdash;
    Satellite (10%) : DBMF permanent
  </div>
</body>
</html>"""


# ──────────────────────────────────────────────────────────────────────────────
# Rapport mensuel
# ──────────────────────────────────────────────────────────────────────────────

def generate_monthly_report(
    ranked_macro: pd.DataFrame,
    top_n_macro: list[dict],
    current_macro: list[dict],
    ranked_thematic: pd.DataFrame,
    top_n_thematic: list[dict],
    current_thematic: list[dict],
    ranked_satellite: pd.DataFrame,
    top_n_satellite: list[dict],
    current_satellite: list[dict],
    spy_ret_1m: float | None,
    ief_ret_1m: float | None,
    portfolio_weights: dict,
    run_date: date | None = None,
    confirm_url: str | None = None,
) -> str:
    run_date = run_date or date.today()

    summary_html = _summary_monthly(
        strategies=[
            {"label": "Macro",      "portfolio_weight": portfolio_weights.get("macro", 0.45),
             "top_n": top_n_macro,     "current": current_macro},
            {"label": "Thématique", "portfolio_weight": portfolio_weights.get("thematic", 0.45),
             "top_n": top_n_thematic,  "current": current_thematic},
            {"label": "Satellite",  "portfolio_weight": portfolio_weights.get("satellite", 0.10),
             "top_n": top_n_satellite, "current": current_satellite},
        ],
        spy_ret_1m=spy_ret_1m,
        ief_ret_1m=ief_ret_1m,
    )

    macro_content, macro_action = _monthly_strategy_block(
        ranked=ranked_macro,
        top_n=top_n_macro,
        current=current_macro,
        top2_m1_label="M3-skip",
        top2_m1_key="ret_3m",
        top2_m2_label="M6-skip",
        top2_m2_key="ret_6m",
        rank_col1_label="M3-skip",
        rank_col1_key="ret_3m",
        rank_col2_label="M6-skip",
        rank_col2_key="ret_6m",
        ma_label="MM200j",
    )

    thematic_content, thematic_action = _monthly_strategy_block(
        ranked=ranked_thematic,
        top_n=top_n_thematic,
        current=current_thematic,
        top2_m1_label="M1",
        top2_m1_key="ret_1m",
        top2_m2_label="M3",
        top2_m2_key="ret_3m",
        rank_col1_label="M1",
        rank_col1_key="ret_1m",
        rank_col2_label="M3",
        rank_col2_key="ret_3m",
        ma_label="MM150j",
    )

    satellite_content, satellite_action = _monthly_strategy_block(
        ranked=ranked_satellite,
        top_n=top_n_satellite,
        current=current_satellite,
        top2_m1_label="M1",
        top2_m1_key="ret_1m",
        top2_m2_label="Score",
        top2_m2_key="score",
        rank_col1_label="M1",
        rank_col1_key="ret_1m",
        rank_col2_label="Score",
        rank_col2_key="score",
        ma_label="—",
    )

    any_action = macro_action or thematic_action or satellite_action
    cta_html   = _cta_button(confirm_url) if any_action else ""

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

  {summary_html}

  <div class="strategy-header" style="margin-top:0;">Stratégie Macro &mdash; 21 ETFs</div>
  {macro_content}

  <div class="strategy-header">Stratégie Thématique &mdash; 10 ETFs</div>
  {thematic_content}

  <div class="strategy-header">Satellite &mdash; Managed Futures</div>
  {satellite_content}

  {cta_html}

  <div class="footer">
    Nisabā &mdash; {run_date.strftime('%d/%m/%Y')} &mdash;
    Macro (45%) : 50% M3-skip + 50% M6-skip · MM200j &mdash;
    Thématique (45%) : 60% M1 + 40% M3 · MM150j &mdash;
    Satellite (10%) : DBMF permanent
  </div>
</body>
</html>"""
