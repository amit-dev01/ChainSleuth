"""
Periodic background worker monitoring suspect wallets for active fund movements.
Triggers immediate alerts to Investigating Officers when mule accounts move stolen funds.
"""

import asyncio
import logging
import time
from typing import Dict, Any, List

from backend.config.chains import ChainType
from backend.storage.redis_client import redis_client
from backend.tasks.celery_app import celery_app
from backend.tracer.engine import tracer_engine

logger = logging.getLogger(__name__)


async def _check_monitored_wallets() -> int:
    """Scan monitored wallets for newly confirmed blockchain transactions."""
    # Retrieve monitored wallet list from Redis registry
    monitored_wallets = await redis_client.get_json("monitored_wallets") or []
    if not monitored_wallets:
        return 0

    alerts_generated = 0
    for item in monitored_wallets:
        address = item.get("address")
        chain_str = item.get("chain", "tron")
        case_id = item.get("case_id", "GENERAL")
        last_checked = item.get("last_checked", int(time.time()) - 3600)

        chain = ChainType(chain_str.lower())
        adapter = tracer_engine.get_adapter(chain)

        try:
            transfers = await adapter.get_transfers(
                address=address,
                limit=10,
                start_timestamp=last_checked
            )

            if transfers:
                logger.info(
                    "ALERT: Detected %d new transactions on monitored wallet %s",
                    len(transfers), address
                )
                alerts_generated += len(transfers)

                # Store alert notification in Redis queue
                for tx in transfers:
                    alert_record = {
                        "alert_id": f"alert_{tx.tx_hash[:12]}",
                        "case_id": case_id,
                        "address": address,
                        "chain": chain.value,
                        "amount": tx.amount,
                        "token": tx.token_symbol,
                        "counterparty": tx.to_address if tx.from_address.lower() == address.lower() else tx.from_address,
                        "direction": "OUTGOING" if tx.from_address.lower() == address.lower() else "INCOMING",
                        "timestamp": tx.timestamp,
                        "message": f"Suspicious transfer of {tx.amount:.2f} {tx.token_symbol} detected on {address[:12]}..."
                    }
                    await redis_client.set_json(f"alert:{alert_record['alert_id']}", alert_record, expire_seconds=86400 * 3)

                # Update last checked timestamp
                item["last_checked"] = int(time.time())

        except Exception as exc:
            logger.error("Error monitoring wallet %s: %s", address, exc)

    await redis_client.set_json("monitored_wallets", monitored_wallets, expire_seconds=86400 * 30)
    return alerts_generated


@celery_app.task(name="backend.tasks.alert_task.monitor_active_wallets")
def monitor_active_wallets() -> Dict[str, Any]:
    """Celery beat periodic task scanning monitored suspect addresses."""
    logger.info("Executing periodic wallet monitoring scan...")
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        count = loop.run_until_complete(_check_monitored_wallets())
        loop.close()
        return {"status": "SUCCESS", "alerts_generated": count}
    except Exception as exc:
        logger.error("Error in monitor_active_wallets task: %s", exc)
        return {"status": "FAILED", "error": str(exc)}
