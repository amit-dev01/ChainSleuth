"""
Asynchronous webhook dispatcher for pushing alerts to external LEA systems (CCTNS / 1930 portal).
"""

import logging
from typing import Dict, Any
import httpx

logger = logging.getLogger(__name__)


async def send_webhook_alert(url: str, payload: Dict[str, Any]) -> bool:
    """
    Deliver forensic alert payload to an external LEA HTTP webhook endpoint.
    """
    if not url:
        return False

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(url, json=payload)
            if response.status_code in (200, 201, 202, 204):
                logger.info("Webhook alert delivered successfully to %s", url)
                return True
            else:
                logger.warning("Webhook alert failed with HTTP %d: %s", response.status_code, response.text[:100])
                return False
    except Exception as exc:
        logger.error("Error dispatching webhook alert to %s: %s", url, exc)
        return False
