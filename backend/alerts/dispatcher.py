"""
Unified alert dispatcher routing priority events to configured LEA communication channels.
"""

import logging
from typing import Dict, Any, Optional

from backend.alerts.channels.email import send_email_alert
from backend.alerts.channels.webhook import send_webhook_alert
from backend.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class AlertDispatcher:
    """Dispatches real-time forensic fraud notifications."""

    @staticmethod
    async def dispatch_vasp_attribution_alert(
        case_id: str,
        seed_address: str,
        vasp_name: str,
        attributed_amount: float,
        terminal_address: str,
        io_email: Optional[str] = None
    ) -> Dict[str, bool]:
        """
        Notify investigators immediately when stolen funds arrive at an exchange deposit address.
        """
        subject = f"[CRITICAL FREEZE REQUISITION] Case {case_id}: {attributed_amount:.2f} USDT tracked to {vasp_name}"
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; color: #333;">
            <div style="background-color: #002b49; color: white; padding: 10px; text-align: center;">
                <h2>ChainSleuth LEA Alert: Destination VASP Reached</h2>
            </div>
            <div style="padding: 15px;">
                <p>Dear Investigating Officer,</p>
                <p>Forensic tracing has identified that stolen funds from suspect wallet <code>{seed_address}</code> have terminated at a known Virtual Asset Service Provider:</p>
                <ul>
                    <li><strong>Destination Exchange:</strong> {vasp_name}</li>
                    <li><strong>Deposit / Terminal Address:</strong> <code>{terminal_address}</code></li>
                    <li><strong>Amount to Freeze:</strong> {attributed_amount:.2f} USDT</li>
                    <li><strong>Case / FIR Ref:</strong> {case_id}</li>
                </ul>
                <p><strong>Action:</strong> Issue immediate Section 91 CrPC requisition to compliance officers to freeze assets before withdrawal.</p>
            </div>
        </body>
        </html>
        """

        payload = {
            "event": "VASP_ATTRIBUTION_DISCOVERED",
            "case_id": case_id,
            "seed_address": seed_address,
            "vasp_name": vasp_name,
            "terminal_address": terminal_address,
            "attributed_amount": attributed_amount,
            "severity": "CRITICAL"
        }

        webhook_success = False
        if settings.ALERT_WEBHOOK_URL:
            webhook_success = await send_webhook_alert(settings.ALERT_WEBHOOK_URL, payload)

        email_success = False
        target_email = io_email or settings.SMTP_FROM_EMAIL
        if target_email:
            email_success = await send_email_alert(target_email, subject, html_body)

        return {"webhook": webhook_success, "email": email_success}


alert_dispatcher = AlertDispatcher()
