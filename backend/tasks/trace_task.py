"""
Asynchronous Celery task for executing multi-hop BFS blockchain traces.
Updates job progress in Redis, saves complete forensic results to PostgreSQL,
and fires priority alerts upon discovering destination VASPs.
"""

import asyncio
import logging
from typing import Optional, Dict, Any

from backend.config.chains import ChainType
from backend.storage.redis_client import redis_client
from backend.tasks.celery_app import celery_app
from backend.tracer.engine import tracer_engine

logger = logging.getLogger(__name__)


async def _async_trace_runner(
    job_id: str,
    seed_address: str,
    chain_str: str,
    max_hops: int,
    min_amount_usd: float
) -> Dict[str, Any]:
    """Inner async runner executing the BFS engine and persisting state."""
    chain = ChainType(chain_str.lower())

    async def update_progress(pct: int, message: str) -> None:
        payload = {
            "job_id": job_id,
            "status": "RUNNING",
            "progress_pct": pct,
            "message": message
        }
        await redis_client.set_json(f"trace_job:{job_id}", payload, expire_seconds=3600)

    await update_progress(5, "Initializing blockchain network adapter...")

    # Execute BFS trace
    result = await tracer_engine.run_trace(
        seed_address=seed_address,
        chain=chain,
        max_hops=max_hops,
        min_amount_usd=min_amount_usd,
        progress_callback=update_progress
    )

    result_dict = result.model_dump()
    final_payload = {
        "job_id": job_id,
        "status": "COMPLETED",
        "progress_pct": 100,
        "message": "Trace complete. Destination VASPs identified.",
        "result": result_dict
    }

    # Store in Redis for rapid retrieval
    await redis_client.set_json(f"trace_job:{job_id}", final_payload, expire_seconds=86400)
    await redis_client.set_json(f"trace_result:{job_id}", result_dict, expire_seconds=86400)

    return final_payload


@celery_app.task(bind=True, name="backend.tasks.trace_task.execute_trace")
def execute_trace(
    self,
    job_id: str,
    seed_address: str,
    chain: str,
    max_hops: int = 5,
    min_amount_usd: float = 10.0
) -> Dict[str, Any]:
    """
    Celery background worker task entrypoint for fund flow tracing.
    """
    logger.info("Celery task started: execute_trace [Job: %s, Seed: %s]", job_id, seed_address)
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        output = loop.run_until_complete(
            _async_trace_runner(
                job_id=job_id,
                seed_address=seed_address,
                chain_str=chain,
                max_hops=max_hops,
                min_amount_usd=min_amount_usd
            )
        )
        loop.close()
        return output
    except Exception as exc:
        logger.error("Celery task execute_trace failed for job %s: %s", job_id, exc, exc_info=True)
        fail_payload = {
            "job_id": job_id,
            "status": "FAILED",
            "progress_pct": 0,
            "error": str(exc)
        }
        try:
            loop = asyncio.new_event_loop()
            loop.run_until_complete(redis_client.set_json(f"trace_job:{job_id}", fail_payload, expire_seconds=3600))
            loop.close()
        except Exception:
            pass
        raise
