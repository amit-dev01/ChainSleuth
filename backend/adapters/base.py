"""
Abstract base class for all blockchain network adapters.
Provides standard interfaces for transfer retrieval, balance queries,
rate limiting, and resilient HTTP request retries.
"""

from abc import ABC, abstractmethod
import asyncio
import functools
import logging
import time
from typing import List, Optional, Dict, Any, Union, Callable
import httpx

from backend.adapters.models import Transfer, WalletInfo, Chain
from backend.config.chains import ChainType

logger = logging.getLogger(__name__)


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 0.5,
    backoff_factor: float = 2.0,
    retryable_exceptions: tuple = (httpx.RequestError, httpx.HTTPStatusError, asyncio.TimeoutError)
):
    """
    Asynchronous decorator implementing exponential backoff retry for network operations.
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            delay = base_delay
            for attempt in range(1, max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except retryable_exceptions as exc:
                    if attempt == max_retries:
                        logger.error(
                            "Function %s failed after %d attempts: %s",
                            func.__name__, max_retries, exc
                        )
                        raise
                    logger.warning(
                        "Attempt %d/%d for %s failed with %s. Retrying in %.2fs...",
                        attempt, max_retries, func.__name__, exc, delay
                    )
                    await asyncio.sleep(delay)
                    delay *= backoff_factor
                except Exception as exc:
                    logger.error("Non-retryable exception in %s: %s", func.__name__, exc)
                    raise
        return wrapper
    return decorator


class RateLimiter:
    """
    Asynchronous Token Bucket rate limiter (tokens per second per chain).
    """
    def __init__(self, tokens_per_second: float = 10.0, max_tokens: Optional[float] = None) -> None:
        self.rate = float(tokens_per_second)
        self.max_tokens = float(max_tokens if max_tokens is not None else max(1.0, tokens_per_second))
        self.tokens = self.max_tokens
        self.last_update = time.monotonic()
        self._lock: Optional[asyncio.Lock] = None

    def _get_lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def acquire(self, tokens: float = 1.0) -> None:
        """Wait until required tokens are available, then consume them."""
        lock = self._get_lock()
        while True:
            async with lock:
                now = time.monotonic()
                elapsed = now - self.last_update
                self.last_update = now
                self.tokens = min(self.max_tokens, self.tokens + elapsed * self.rate)

                if self.tokens >= tokens:
                    self.tokens -= tokens
                    return

                wait_time = (tokens - self.tokens) / self.rate
            await asyncio.sleep(max(0.01, wait_time))


class BlockchainAdapter(ABC):
    """
    Abstract interface enforcing uniform contract for blockchain providers.
    """

    def __init__(
        self,
        chain: Union[Chain, ChainType, str],
        max_concurrent_requests: int = 5,
        tokens_per_second: float = 10.0
    ) -> None:
        if isinstance(chain, str):
            self.chain = Chain(chain) or Chain.TRON
        elif isinstance(chain, ChainType):
            self.chain = Chain(chain.name)
        else:
            self.chain = chain

        self.max_concurrent_requests = max_concurrent_requests
        self.rate_limiter = RateLimiter(tokens_per_second=tokens_per_second)
        self._semaphore: Optional[asyncio.Semaphore] = None
        self.client: Optional[httpx.AsyncClient] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def get_semaphore(self) -> asyncio.Semaphore:
        """Get or initialize semaphore in the active event loop."""
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None

        if self._semaphore is None or self._loop != current_loop:
            self._loop = current_loop
            self._semaphore = asyncio.Semaphore(self.max_concurrent_requests)
        return self._semaphore

    @property
    def semaphore(self) -> asyncio.Semaphore:
        """Property accessor for semaphore."""
        return self.get_semaphore()

    async def get_client(self) -> httpx.AsyncClient:
        """Get or initialize the reusable async HTTP client bound to current loop."""
        current_loop = asyncio.get_running_loop()
        if self.client is None or self.client.is_closed or self._loop != current_loop:
            self._loop = current_loop
            self._semaphore = asyncio.Semaphore(self.max_concurrent_requests)
            self.client = httpx.AsyncClient(
                timeout=httpx.Timeout(15.0, connect=5.0),
                limits=httpx.Limits(max_keepalive_connections=20, max_connections=50)
            )
        return self.client

    async def close(self) -> None:
        """Gracefully close HTTP client connection."""
        if self.client and not self.client.is_closed:
            await self.client.aclose()

    async def _request_with_retry(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        max_retries: int = 2,
        base_delay: float = 0.5
    ) -> Optional[Dict[str, Any]]:
        """
        Execute an HTTP request with rate-limiting token bucket, concurrency semaphore,
        structured logging, and exponential backoff retry.
        """
        client = await self.get_client()

        for attempt in range(1, max_retries + 1):
            await self.rate_limiter.acquire()
            async with self.semaphore:
                req_start = time.time()
                try:
                    logger.info(
                        "[%s API] %s %s (attempt %d/%d)",
                        self.chain.value, method, url, attempt, max_retries
                    )
                    response = await client.request(
                        method=method,
                        url=url,
                        params=params,
                        headers=headers,
                        json=json_data
                    )
                    duration_ms = (time.time() - req_start) * 1000

                    if response.status_code == 200:
                        logger.debug(
                            "[%s API] %s 200 OK (%.1fms)",
                            self.chain.value, url, duration_ms
                        )
                        return response.json()
                    elif response.status_code == 429:  # Rate limited
                        backoff = base_delay * (2 ** (attempt - 1))
                        logger.warning(
                            "[%s API] Rate limited (429) for %s. Backing off %.2fs (attempt %d/%d)",
                            self.chain.value, url, backoff, attempt, max_retries
                        )
                        await asyncio.sleep(backoff)
                    elif response.status_code in (400, 401, 403):
                        logger.warning(
                            "[%s API] Client error (%d) for %s: %s",
                            self.chain.value, response.status_code, url, response.text[:200]
                        )
                        return None
                    else:
                        logger.warning(
                            "[%s API] HTTP %d for %s (%.1fms): %s",
                            self.chain.value, response.status_code, url, duration_ms, response.text[:200]
                        )
                        if attempt == max_retries:
                            return None
                        await asyncio.sleep(base_delay * attempt)
                except httpx.RequestError as exc:
                    logger.warning(
                        "[%s API] Network error querying %s: %s (attempt %d/%d)",
                        self.chain.value, url, exc, attempt, max_retries
                    )
                    if attempt == max_retries:
                        return None
                    await asyncio.sleep(base_delay * attempt)

        return None

    @abstractmethod
    async def get_outgoing_transfers(self, address: str, limit: int = 50) -> List[Transfer]:
        """Fetch outgoing transfers for an address."""
        pass

    @abstractmethod
    async def get_incoming_transfers(self, address: str, limit: int = 50) -> List[Transfer]:
        """Fetch incoming transfers for an address."""
        pass

    @abstractmethod
    async def get_balance(self, address: str) -> WalletInfo:
        """Fetch native balance and token balances for an address."""
        pass

    @abstractmethod
    async def get_token_transfers(
        self,
        address: str,
        token_contract: Optional[str] = None
    ) -> List[Transfer]:
        """Fetch token transfers for an address optionally filtered by contract."""
        pass

    @abstractmethod
    async def get_first_seen(self, address: str) -> int:
        """Fetch unix timestamp in seconds when address was first active."""
        pass

    async def get_transfers(
        self,
        address: str,
        contract_address: Optional[str] = None,
        limit: int = 50,
        start_timestamp: Optional[int] = None
    ) -> List[Transfer]:
        """
        Unified method for retrieving transfers (used by BFS tracing engine).
        Retrieves outgoing transfers and filters by start timestamp.
        """
        transfers = await self.get_outgoing_transfers(address, limit=limit)
        if start_timestamp:
            transfers = [t for t in transfers if t.timestamp >= start_timestamp]
        return transfers

    @abstractmethod
    async def validate_address(self, address: str) -> bool:
        """Verify if address is syntactically valid for this network."""
        pass


# Backward compatibility alias
BaseAdapter = BlockchainAdapter


def get_adapter(chain: Union[Chain, ChainType, str]) -> BlockchainAdapter:
    """
    Factory function returning the appropriate BlockchainAdapter instance for a given chain.
    """
    chain_str = chain.value if hasattr(chain, "value") else str(chain)
    chain_upper = chain_str.upper()

    if "TRON" in chain_upper:
        from backend.adapters.tron_adapter import TronAdapter
        return TronAdapter()
    elif "ETH" in chain_upper:
        from backend.adapters.eth_adapter import EthereumAdapter
        return EthereumAdapter()
    elif "SOL" in chain_upper:
        from backend.adapters.solana_adapter import SolanaAdapter
        return SolanaAdapter()
    else:
        raise ValueError(f"Unsupported blockchain network: {chain}")
