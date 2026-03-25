"""
email_sender.py — Envoi des emails via Gmail API avec authentification OAuth2.

Fonctionnement :
  - Au premier lancement (local) : scripts/setup_gmail_oauth.py génère un refresh token
  - En production (GitHub Actions) : le refresh token est stocké dans les secrets GitHub
  - Le token d'accès est renouvelé automatiquement à chaque run

Variables d'environnement requises :
  GMAIL_CLIENT_ID       → Client ID OAuth2 (depuis Google Cloud Console)
  GMAIL_CLIENT_SECRET   → Client Secret OAuth2
  GMAIL_REFRESH_TOKEN   → Refresh token généré par setup_gmail_oauth.py
  GMAIL_SENDER          → Adresse Gmail associée aux credentials OAuth2
  EMAIL_RECIPIENT       → (optionnel) override du destinataire défini dans settings.yaml
"""

import base64
import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import yaml
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

logger = logging.getLogger(__name__)

_SMTP_HOST = "smtp.gmail.com"
_SMTP_PORT = 587
_TOKEN_URI = "https://oauth2.googleapis.com/token"
_SCOPES = ["https://mail.google.com/"]


class EmailSender:
    def __init__(self, config_path: Path | None = None):
        # Credentials OAuth2
        self.client_id = os.environ.get("GMAIL_CLIENT_ID", "").strip()
        self.client_secret = os.environ.get("GMAIL_CLIENT_SECRET", "").strip()
        self.refresh_token = os.environ.get("GMAIL_REFRESH_TOKEN", "").strip()
        self.sender = os.environ.get("GMAIL_SENDER", "").strip()

        # Destinataire
        recipient_env = os.environ.get("EMAIL_RECIPIENT", "").strip()
        if recipient_env:
            self.recipient = recipient_env
        elif config_path:
            with open(Path(config_path) / "settings.yaml") as f:
                cfg = yaml.safe_load(f)
            self.recipient = cfg["email"]["recipient"]
        else:
            self.recipient = "pebeneteau@gmail.com"

        missing = [
            name for name, val in [
                ("GMAIL_CLIENT_ID", self.client_id),
                ("GMAIL_CLIENT_SECRET", self.client_secret),
                ("GMAIL_REFRESH_TOKEN", self.refresh_token),
                ("GMAIL_SENDER", self.sender),
            ] if not val
        ]
        if missing:
            raise EnvironmentError(
                f"Variables d'environnement manquantes : {', '.join(missing)}\n"
                "→ En local : exporter les variables (voir README).\n"
                "→ GitHub Actions : ajouter les secrets dans Settings → Secrets and variables → Actions.\n"
                "→ Pour obtenir le refresh token : python scripts/setup_gmail_oauth.py"
            )

    # ──────────────────────────────────────────────────────────────────────────
    # API publique
    # ──────────────────────────────────────────────────────────────────────────

    def send(self, subject: str, html_body: str) -> None:
        """Envoie un email HTML au destinataire configuré via Gmail OAuth2."""
        access_token = self._get_access_token()
        msg = self._build_message(subject, html_body)
        self._send_via_smtp(msg, access_token)
        logger.info(f"Email envoyé : « {subject} » → {self.recipient}")

    def send_alert(self, error_message: str) -> None:
        """Envoie un email d'alerte en cas d'échec du pipeline."""
        subject = "🚨 Nisabā — Erreur pipeline"
        html = f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8"></head>
<body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;">
  <h2 style="color:#e74c3c;">🚨 Erreur dans le pipeline Nisabā</h2>
  <p>Une erreur s'est produite lors de l'exécution automatique :</p>
  <pre style="background:#f8f8f8;border-left:4px solid #e74c3c;padding:16px;
              border-radius:4px;white-space:pre-wrap;word-break:break-all;font-size:13px;">
{error_message}
  </pre>
  <p style="color:#666;">Consultez les logs GitHub Actions pour plus de détails.</p>
</body></html>"""
        try:
            self.send(subject, html)
        except Exception as exc:
            logger.error(f"Impossible d'envoyer l'email d'alerte : {exc}")

    # ──────────────────────────────────────────────────────────────────────────
    # Méthodes internes
    # ──────────────────────────────────────────────────────────────────────────

    def _get_access_token(self) -> str:
        """Utilise le refresh token pour obtenir un access token valide."""
        creds = Credentials(
            token=None,
            refresh_token=self.refresh_token,
            token_uri=_TOKEN_URI,
            client_id=self.client_id,
            client_secret=self.client_secret,
            scopes=_SCOPES,
        )
        creds.refresh(Request())
        return creds.token

    def _build_message(self, subject: str, html_body: str) -> MIMEMultipart:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.sender
        msg["To"] = self.recipient
        msg.attach(MIMEText(html_body, "html", "utf-8"))
        return msg

    def _send_via_smtp(self, msg: MIMEMultipart, access_token: str) -> None:
        """Envoie via SMTP Gmail avec XOAUTH2."""
        # Format XOAUTH2 : user=<email>\x01auth=Bearer <token>\x01\x01
        auth_string = f"user={self.sender}\x01auth=Bearer {access_token}\x01\x01"
        auth_b64 = base64.b64encode(auth_string.encode()).decode()

        with smtplib.SMTP(_SMTP_HOST, _SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.docmd("AUTH", f"XOAUTH2 {auth_b64}")
            server.sendmail(self.sender, self.recipient, msg.as_string())
