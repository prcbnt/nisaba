"""Diagnostic script — exécuté en step GitHub Actions pour vérifier les données."""
import sys
import warnings
warnings.filterwarnings('ignore')

sys.path.insert(0, '.')
from pathlib import Path

import yfinance as yf
from src.data_fetcher import DataFetcher
from src.momentum_scorer import MomentumScorer

print(f"yfinance version      = {yf.__version__}")

fetcher = DataFetcher(Path('config'))
print(f"fetch_period_days     = {fetcher.fetch_period_days}")

prices = fetcher.get_processed_prices()
print(f"Lignes DataFrame      = {len(prices)}")
print(f"Colonnes              = {list(prices.columns)}\n")

for strategy in ("macro", "thematic"):
    scorer = MomentumScorer(Path('config'), strategy=strategy)
    print(f"── Stratégie {strategy} (ma_filter={scorer.ma_days}j) ──")
    ranked = scorer.compute_scores(prices)
    for _, r in ranked.iterrows():
        n = len(prices[r['ticker']].dropna())
        print(f"  {r['ticker']:<12} {r['status']:<30} {n} jours")
    eligible = (ranked['status'] == '✓').sum()
    print(f"  → {eligible} éligibles / {len(ranked)}\n")
