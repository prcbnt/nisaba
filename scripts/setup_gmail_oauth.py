#!/usr/bin/env python3
"""
setup_gmail_oauth.py — Génération du refresh token Gmail OAuth2.

À lancer UNE SEULE FOIS en local pour obtenir le refresh token à stocker
dans les secrets GitHub.

Prérequis :
  pip install google-auth-oauthlib

Usage :
  python scripts/setup_gmail_oauth.py

Le script ouvre une page d'autorisation dans le navigateur, puis affiche
les 4 valeurs à copier dans les secrets GitHub.
"""

import json
import sys
import webbrowser
from pathlib import Path

try:
    from google_auth_oauthlib.flow import InstalledAppFlow
except ImportError:
    print("❌ Dépendance manquante. Lancer : pip install google-auth-oauthlib")
    sys.exit(1)

_SCOPES = ["https://mail.google.com/"]

# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    print()
    print("═" * 60)
    print("  Nisabā — Configuration Gmail OAuth2")
    print("═" * 60)
    print()
    print("Ce script génère un refresh token Gmail pour que Nisabā")
    print("puisse envoyer des emails sans mot de passe.")
    print()

    # ── Étape 1 : récupérer le fichier credentials.json ──────────────────────
    print("ÉTAPE 1 — Fichier credentials.json")
    print("-" * 40)
    print("Si vous ne l'avez pas encore :")
    print("  1. Aller sur https://console.cloud.google.com")
    print("  2. Créer un projet (ex. 'Nisabā')")
    print("  3. APIs & Services → Activer 'Gmail API'")
    print("  4. APIs & Services → Credentials → Create Credentials → OAuth client ID")
    print("     Type : 'Desktop app'  |  Nom : 'Nisabā'")
    print("  5. Télécharger le JSON et le placer dans ce dossier")
    print()

    # Chercher credentials.json dans le dossier courant et la racine du projet
    search_paths = [
        Path("credentials.json"),
        Path(__file__).parent.parent / "credentials.json",
        Path.home() / "Downloads" / "credentials.json",
    ]
    creds_path = None
    for p in search_paths:
        if p.exists():
            creds_path = p
            print(f"✅ Fichier trouvé : {creds_path}")
            break

    if not creds_path:
        path_input = input("Chemin vers credentials.json : ").strip().strip("'\"")
        creds_path = Path(path_input)
        if not creds_path.exists():
            print(f"❌ Fichier introuvable : {creds_path}")
            sys.exit(1)

    # ── Étape 2 : flux OAuth2 ─────────────────────────────────────────────────
    print()
    print("ÉTAPE 2 — Autorisation dans le navigateur")
    print("-" * 40)
    print("Une page s'ouvre dans votre navigateur.")
    print("Connectez-vous au compte Gmail qui enverra les emails,")
    print("puis accordez l'accès à l'application.")
    print()
    input("Appuyer sur Entrée pour ouvrir le navigateur…")

    flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), scopes=_SCOPES)
    creds = flow.run_local_server(port=0, open_browser=True)

    # ── Étape 3 : afficher les valeurs à copier ───────────────────────────────
    with open(creds_path) as f:
        client_info = json.load(f)

    client_data = client_info.get("installed") or client_info.get("web", {})
    client_id = client_data.get("client_id", "")
    client_secret = client_data.get("client_secret", "")
    refresh_token = creds.refresh_token
    sender_email = input("\nAdresse Gmail de ce compte (celle qui enverra les emails) : ").strip()

    print()
    print("═" * 60)
    print("  ✅ Autorisation accordée ! Voici vos secrets GitHub :")
    print("═" * 60)
    print()
    print("Aller dans : GitHub repo → Settings → Secrets and variables")
    print("             → Actions → New repository secret")
    print()
    print(f"  GMAIL_CLIENT_ID      =  {client_id}")
    print(f"  GMAIL_CLIENT_SECRET  =  {client_secret}")
    print(f"  GMAIL_REFRESH_TOKEN  =  {refresh_token}")
    print(f"  GMAIL_SENDER         =  {sender_email}")
    print()
    print("⚠️  Ne jamais commiter ces valeurs dans le repo.")
    print("    Supprimer credentials.json du dossier une fois terminé.")
    print("═" * 60)
    print()

    # Optionnel : sauvegarder dans un .env local (non commité)
    save = input("Sauvegarder dans .env.local pour les tests en local ? (o/N) : ").strip().lower()
    if save == "o":
        env_path = Path(__file__).parent.parent / ".env.local"
        with open(env_path, "w") as f:
            f.write(f"GMAIL_CLIENT_ID={client_id}\n")
            f.write(f"GMAIL_CLIENT_SECRET={client_secret}\n")
            f.write(f"GMAIL_REFRESH_TOKEN={refresh_token}\n")
            f.write(f"GMAIL_SENDER={sender_email}\n")
        print(f"✅ Sauvegardé dans {env_path}")
        print("   Pour l'utiliser : source .env.local  (ou export manuellement)")
        print("   ⚠️  Ce fichier est dans .gitignore — ne pas le commiter.")


if __name__ == "__main__":
    main()
