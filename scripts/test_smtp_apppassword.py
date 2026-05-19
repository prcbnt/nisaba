#!/usr/bin/env python3
"""
test_smtp_apppassword.py — Vérifie que l'envoi via App Password fonctionne.

Usage :
  GMAIL_SENDER=toi@gmail.com GMAIL_APP_PASSWORD="xxxx xxxx xxxx xxxx" \
    python scripts/test_smtp_apppassword.py

Le script envoie un email de test à GMAIL_SENDER lui-même (ou EMAIL_RECIPIENT
si défini). Il affiche OK ou l'erreur exacte.
"""

import os
import smtplib
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587

sender       = os.environ.get("GMAIL_SENDER", "").strip()
app_password = os.environ.get("GMAIL_APP_PASSWORD", "").replace(" ", "").strip()
recipient    = os.environ.get("EMAIL_RECIPIENT", sender)

if not sender or not app_password:
    print("❌ Variables manquantes.")
    print("   Lancer avec :")
    print('   GMAIL_SENDER=toi@gmail.com GMAIL_APP_PASSWORD="xxxx xxxx xxxx xxxx" python scripts/test_smtp_apppassword.py')
    sys.exit(1)

print(f"Sender    : {sender}")
print(f"Recipient : {recipient}")
print(f"Password  : {'*' * len(app_password)} ({len(app_password)} chars)")
print()

msg = MIMEMultipart("alternative")
msg["Subject"] = "Nisabā — Test SMTP App Password ✓"
msg["From"]    = sender
msg["To"]      = recipient
msg.attach(MIMEText(
    "<html><body style='font-family:Helvetica,sans-serif;padding:20px;'>"
    "<h3>✅ Test SMTP réussi</h3>"
    "<p>L'envoi via App Password fonctionne. Nisabā peut migrer de OAuth2 vers App Password.</p>"
    "</body></html>",
    "html", "utf-8"
))

try:
    print("Connexion à smtp.gmail.com:587…")
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        print("Authentification…")
        server.login(sender, app_password)
        print("Envoi…")
        server.sendmail(sender, recipient, msg.as_string())
    print()
    print("✅ OK — email envoyé. Vérifie ta boîte.")
    print()
    print("Tu peux maintenant lancer la migration :")
    print("  → Ajouter GMAIL_APP_PASSWORD dans les secrets GitHub")
    print("  → Supprimer GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, GMAIL_REFRESH_TOKEN")

except smtplib.SMTPAuthenticationError as e:
    print(f"\n❌ Erreur d'authentification : {e}")
    print("   Vérifie que :")
    print("   1. La 2FA est activée sur le compte Gmail")
    print("   2. L'App Password est correct (16 chars, espaces ignorés)")
    print("   3. L'App Password n'a pas été révoqué")
    sys.exit(1)
except Exception as e:
    print(f"\n❌ Erreur : {e}")
    sys.exit(1)
