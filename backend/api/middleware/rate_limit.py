"""
Sliding-window rate limiter dependency using Redis.
Prevents API flooding and protects downstream blockchain node providers.
"""

import logging
from fastapi import Request, HTTPException, status
from backend.storage.redis_client import redis_client

logger = logging.getLogger(__name__)


async def rate_limiter(request: Request) -> None:
    """
    Enforce rate limits on incoming API requests (e.g. 60 requests per minute per IP).
    """
    client_ip = request.client.host if request.client else "127.0.0.1"
    endpoint = request.url.path

    identifier = f"{client_ip}:{endpoint}"
    # Allow 120 requests per 60 seconds
    allowed = await redis_client.check_rate_limit(identifier, limit=120, period=60)

    if not allowed:
        logger.warning("Rate limit exceeded for client %s on endpoint %s", client_ip, endpoint)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please throttle your requests to ChainSleuth API."
        )
