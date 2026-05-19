"""
email_sender.py — Envoi des emails via Gmail SMTP + App Password.

Variables d'environnement requises :
  GMAIL_SENDER        → Adresse Gmail expéditrice
  GMAIL_APP_PASSWORD  → App Password généré dans Google Account → Security
  EMAIL_RECIPIENT     → (optionnel) override du destinataire défini dans settings.yaml
"""

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

_SMTP_HOST = "smtp.gmail.com"
_SMTP_PORT = 587


class EmailSender:
    def __init__(self, config_path: Path | None = None):
        self.sender       = os.environ.get("GMAIL_SENDER", "").strip()
        # Supprime tous les espaces blancs (espaces, tabs, retours à la ligne)
        # pour éviter les problèmes de copier-coller depuis un secret GitHub
        import re
        raw = os.environ.get("GMAIL_APP_PASSWORD", "")
        self.app_password = re.sub(r"\s", "", raw)

        recipient_env = os.environ.get("EMAIL_RECIPIENT", "").strip()
        if recipient_env:
            self.recipient = recipient_env
        elif config_path:
            with open(Path(config_path) / "settings.yaml") as f:
                cfg = yaml.safe_load(f)
            self.recipient = cfg["email"]["recipient"]
        else:
            self.recipient = "pebeneteau@gmail.com"

        logger.info(f"EmailSender — sender={self.sender!r}  app_password_len={len(self.app_password)}")

        missing = [
            name for name, val in [
                ("GMAIL_SENDER", self.sender),
                ("GMAIL_APP_PASSWORD", self.app_password),
            ] if not val
        ]
        if missing:
            raise EnvironmentError(
                f"Variables d'environnement manquantes : {', '.join(missing)}\n"
                "→ En local : exporter GMAIL_SENDER et GMAIL_APP_PASSWORD.\n"
                "→ GitHub Actions : ajouter les secrets dans Settings → Secrets and variables → Actions."
            )

    # ──────────────────────────────────────────────────────────────────────────
    # API publique
    # ──────────────────────────────────────────────────────────────────────────

    def send(self, subject: str, html_body: str) -> None:
        """Envoie un email HTML au destinataire configuré via Gmail SMTP."""
        msg = self._build_message(subject, html_body)
        self._send_via_smtp(msg)
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

    def _build_message(self, subject: str, html_body: str) -> MIMEMultipart:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = self.sender
        msg["To"]      = self.recipient
        msg.attach(MIMEText(html_body, "html", "utf-8"))
        return msg

    def _send_via_smtp(self, msg: MIMEMultipart) -> None:
        with smtplib.SMTP(_SMTP_HOST, _SMTP_PORT, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(self.sender, self.app_password)
            server.sendmail(self.sender, self.recipient, msg.as_string())
