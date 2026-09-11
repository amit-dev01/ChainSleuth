"""
Redis cache, rate-limiting, and distributed state storage client.
Includes seamless in-memory fallback if Redis is not running locally.
"""

import json
import logging
import time
from typing import Any, Optional, Dict

try:
    import redis.asyncio as aioredis
    from redis.exceptions import ConnectionError as RedisConnectionError
except ImportError:
    aioredis = None
    RedisConnectionError = Exception

from backend.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class RedisClient:
    """Async Redis client wrapper with graceful fallback for development."""

    def __init__(self) -> None:
        self._redis: Optional[Any] = None
        self._in_memory_fallback: Dict[str, Dict[str, Any]] = {}
        self._connected: bool = False

    async def connect(self) -> None:
        """Establish connection pool to Redis server."""
        if aioredis is None:
            self._connected = False
            logger.info("redis package not installed. Using high-performance in-memory state engine.")
            return

        try:
            self._redis = aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                socket_timeout=2.0
            )
            await self._redis.ping()
            self._connected = True
            logger.info("Connected to Redis successfully at %s", settings.REDIS_URL)
        except Exception as exc:
            self._connected = False
            logger.warning(
                "Could not connect to Redis at %s: %s. Using in-memory fallback.",
                settings.REDIS_URL, exc
            )

    async def close(self) -> None:
        """Close connection to Redis."""
        if self._redis and self._connected:
            await self._redis.close()
            self._connected = False

    async def get_json(self, key: str) -> Optional[Any]:
        """Fetch and deserialize JSON value by key."""
        if self._connected and self._redis:
            try:
                val = await self._redis.get(key)
                return json.loads(val) if val else None
            except Exception as exc:
                logger.error("Redis get_json error for key %s: %s", key, exc)

        # In-memory fallback
        item = self._in_memory_fallback.get(key)
        if item:
            if item["expires_at"] and item["expires_at"] < time.time():
                del self._in_memory_fallback[key]
                return None
            return item["data"]
        return None

    async def set_json(self, key: str, value: Any, expire_seconds: int = 3600) -> bool:
        """Serialize and store a JSON value with TTL."""
        if self._connected and self._redis:
            try:
                payload = json.dumps(value, default=str)
                await self._redis.set(key, payload, ex=expire_seconds)
                return True
            except Exception as exc:
                logger.error("Redis set_json error for key %s: %s", key, exc)

        # In-memory fallback
        expires_at = time.time() + expire_seconds if expire_seconds else None
        self._in_memory_fallback[key] = {
            "data": value,
            "expires_at": expires_at
        }
        return True

    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        if self._connected and self._redis:
            try:
                await self._redis.delete(key)
                return True
            except Exception as exc:
                logger.error("Redis delete error for key %s: %s", key, exc)

        self._in_memory_fallback.pop(key, None)
        return True

    async def check_rate_limit(self, identifier: str, limit: int, period: int) -> bool:
        """
        Sliding-window rate limiter.
        Returns True if request is ALLOWED, False if limit exceeded.
        """
        now = time.time()
        key = f"rate_limit:{identifier}"

        if self._connected and self._redis:
            try:
                pipe = self._redis.pipeline()
                pipe.zremrangebyscore(key, 0, now - period)
                pipe.zadd(key, {str(now): now})
                pipe.zcard(key)
                pipe.expire(key, period)
                results = await pipe.execute()
                current_count = results[2]
                return current_count <= limit
            except Exception as exc:
                logger.error("Redis rate limit error: %s. Permitting request.", exc)
                return True

        # In-memory rate limiting fallback
        record = self._in_memory_fallback.get(key, {"data": []})
        timestamps = [ts for ts in record["data"] if ts > now - period]
        if len(timestamps) >= limit:
            return False
        timestamps.append(now)
        self._in_memory_fallback[key] = {"data": timestamps, "expires_at": now + period}
        return True


# Global client instance
redis_client = RedisClient()


async def get_redis() -> RedisClient:
    """FastAPI dependency for Redis client."""
    return redis_client
