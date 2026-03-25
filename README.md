# Nisabā

Pipeline automatisé de screening momentum pour un portefeuille de 21 ETFs (3 zones × 7 secteurs). Chaque lundi : email de suivi hebdomadaire. Premier lundi du mois : email de rebalancement.

**Stratégie** : Score composite 50% M1 + 50% M3 · Filtre absolu MM200j · Allocation 50% Top 1 / 50% Top 2

---

## Structure du projet

```
nisaba/
├── config/
│   ├── tickers.yaml        # Univers des 21 ETFs
│   └── settings.yaml       # Paramètres (poids, filtre, email…)
├── data/
│   ├── portfolio_state.json  # Allocation courante (mis à jour automatiquement)
│   └── backtest_results.csv  # Généré par run_backtest.py
├── src/
│   ├── data_fetcher.py     # Téléchargement yfinance + conversion EUR→USD
│   ├── momentum_scorer.py  # Calcul des scores + filtre MM200j
│   ├── portfolio.py        # Gestion de l'état du portefeuille
│   ├── email_sender.py     # Envoi Gmail SMTP
│   ├── report_generator.py # Génération des emails HTML
│   └── backtester.py       # Backtest historique
├── scripts/
│   ├── run_weekly.py       # Rapport hebdomadaire
│   ├── run_monthly.py      # Rapport mensuel + rebalancement
│   └── run_backtest.py     # Backtest sur historique
├── .github/workflows/
│   └── monday.yml          # GitHub Actions (chaque lundi)
└── requirements.txt
```

---

## Installation locale

```bash
git clone https://github.com/prcbnt/nisaba.git
cd nisaba
pip3 install -r requirements.txt
```

---

## Configuration Gmail OAuth2

Le pipeline utilise l'API Gmail avec OAuth2 — aucun mot de passe ni App Password requis.

### Étape 1 — Créer les credentials Google Cloud (5 min)

1. Aller sur [console.cloud.google.com](https://console.cloud.google.com)
2. Créer un projet (ex. `Nisabā`)
3. **APIs & Services → Bibliothèque** → activer **Gmail API**
4. **APIs & Services → Identifiants → Créer des identifiants → ID client OAuth**
   - Type : **Application de bureau**  |  Nom : `Nisabā`
5. Télécharger le fichier JSON généré et le placer à la racine du repo sous le nom `credentials.json`

> `credentials.json` est dans `.gitignore` — il ne sera jamais commité.

### Étape 2 — Générer le refresh token (une seule fois)

```bash
pip3 install google-auth-oauthlib
python3 scripts/setup_gmail_oauth.py
```

Le script ouvre le navigateur, vous demande d'autoriser l'accès à votre compte Gmail, puis affiche les 4 valeurs à copier dans GitHub.

### Étape 3 — En local, exporter les variables

```bash
export GMAIL_CLIENT_ID="votre-client-id.apps.googleusercontent.com"
export GMAIL_CLIENT_SECRET="GOCSPX-..."
export GMAIL_REFRESH_TOKEN="1//..."
export GMAIL_SENDER="votre.adresse@gmail.com"
# EMAIL_RECIPIENT est optionnel (défaut : pebeneteau@gmail.com)
```

Le script de setup propose de sauvegarder ces valeurs dans `.env.local` (également dans `.gitignore`).

---

## Déploiement GitHub Actions

### 1. Créer le repository

```bash
git init
git add .
git commit -m "feat: init Nisabā pipeline"
git remote add origin https://github.com/prcbnt/nisaba.git
git push -u origin main
```

### 2. Ajouter les secrets GitHub

Dans le repo GitHub : **Settings → Secrets and variables → Actions → New repository secret**

| Secret | Valeur |
|--------|--------|
| `GMAIL_CLIENT_ID` | Client ID OAuth2 (`.apps.googleusercontent.com`) |
| `GMAIL_CLIENT_SECRET` | Client Secret OAuth2 (`GOCSPX-…`) |
| `GMAIL_REFRESH_TOKEN` | Refresh token généré par `setup_gmail_oauth.py` |
| `GMAIL_SENDER` | Adresse Gmail autorisée |
| `EMAIL_RECIPIENT` | (optionnel) Override du destinataire |

### 3. Activer GitHub Actions

Le workflow `.github/workflows/monday.yml` se déclenche automatiquement chaque lundi à 07h30 UTC. Aucune action supplémentaire nécessaire.

**Déclencher manuellement** (pour tester) : GitHub → Actions → Nisabā — Monday Run → Run workflow.

---

## Utilisation en local

### Rapport hebdomadaire

```bash
python3 scripts/run_weekly.py
```

### Rapport mensuel (rebalancement)

```bash
python3 scripts/run_monthly.py
```

### Backtest

```bash
# Backtest depuis 2020 (défaut dans settings.yaml)
python3 scripts/run_backtest.py

# Backtest sur une période personnalisée
python3 scripts/run_backtest.py --start 2018-01-01 --end 2024-12-31

# Résultats exportés dans data/backtest_results.csv
```

---

## Personnalisation

**Modifier l'univers d'ETFs** : éditer `config/tickers.yaml` (ajouter/retirer des tickers, ajuster les tickers EUR dans `eur_tickers`).

**Modifier les poids du score** : éditer `config/settings.yaml` (`weight_1m`, `weight_3m`).

**Modifier l'horaire d'envoi** : éditer `.github/workflows/monday.yml` (ligne `cron:`).

---

## Note sur EUAD

Le ticker `EUAD` (iShares MSCI Europe Aerospace & Defense) est référencé comme coté en USD sur CBOE Europe. Il n'est donc **pas** dans la liste `eur_tickers` du fichier de config. Si vous constatez que les cours sont en EUR (vérifier avec `yf.Ticker("EUAD").info`), ajouter `EUAD` dans la liste `eur_tickers` de `config/tickers.yaml`.

---

## Variables d'environnement

| Variable | Obligatoire | Description |
|----------|-------------|-------------|
| `GMAIL_CLIENT_ID` | ✅ | Client ID OAuth2 Google Cloud |
| `GMAIL_CLIENT_SECRET` | ✅ | Client Secret OAuth2 Google Cloud |
| `GMAIL_REFRESH_TOKEN` | ✅ | Refresh token généré par `setup_gmail_oauth.py` |
| `GMAIL_SENDER` | ✅ | Adresse Gmail associée aux credentials |
| `EMAIL_RECIPIENT` | ➖ | Override du destinataire (défaut dans settings.yaml) |
