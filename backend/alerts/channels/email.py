"""
SMTP email dispatcher for delivering critical asset freeze alerts to Cyber Cell IOs.
"""

import asyncio
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import logging
import smtplib

from backend.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


async def send_email_alert(recipient_email: str, subject: str, html_body: str) -> bool:
    """
    Dispatch email notification via configured SMTP server.
    """
    if not settings.SMTP_USER or not settings.SMTP_HOST:
        logger.info("SMTP credentials not configured. Simulated dispatch of email to %s: %s", recipient_email, subject)
        return True

    def _sync_send() -> bool:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = settings.SMTP_FROM_EMAIL
            msg["To"] = recipient_email

            part = MIMEText(html_body, "html")
            msg.attach(part)

            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
                server.starttls()
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(settings.SMTP_FROM_EMAIL, [recipient_email], msg.as_string())

            logger.info("Alert email successfully dispatched to %s", recipient_email)
            return True
        except Exception as exc:
            logger.error("Failed sending email alert to %s: %s", recipient_email, exc)
            return False

    return await asyncio.to_thread(_sync_send)
