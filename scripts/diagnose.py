"""Diagnostic script — exécuté en step GitHub Actions pour vérifier les données."""
import sys
import warnings
warnings.filterwarnings('ignore')

sys.path.insert(0, '.')
from src.data_fetcher import DataFetcher
from src.momentum_scorer import MomentumScorer
from pathlib import Path

import yfinance as yf
print(f"yfinance version      = {yf.__version__}")

fetcher = DataFetcher(Path('config'))
scorer  = MomentumScorer(Path('config'))

print(f"fetch_period_days     = {fetcher.fetch_period_days}")
print(f"ma_filter_days        = {scorer.ma_days}")

prices = fetcher.get_processed_prices()
print(f"Lignes DataFrame      = {len(prices)}")
print(f"Colonnes              = {list(prices.columns)}\n")

ranked = scorer.compute_scores(prices)
for _, r in ranked.iterrows():
    n = len(prices[r['ticker']].dropna())
    print(f"  {r['ticker']:<12} {r['status']:<26} {n} jours")

eligible = (ranked['status'] == '✓').sum()
print(f"\n→ {eligible} éligibles / {len(ranked)}")
