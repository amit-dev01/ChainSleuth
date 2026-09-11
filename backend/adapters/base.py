"""
Abstract base class for all blockchain network adapters.
Provides standard interfaces for transfer retrieval, balance queries,
rate limiting, and resilient HTTP request retries.
"""

from abc import ABC, abstractmethod
import asyncio
import logging
from typing import List, Optional, Dict, Any
import httpx

from backend.adapters.models import Transfer, TxInfo, WalletBalance
from backend.config.chains import ChainType

logger = logging.getLogger(__name__)


class BaseAdapter(ABC):
    """Abstract interface enforcing uniform contract for blockchain providers."""

    def __init__(self, chain: ChainType, max_concurrent_requests: int = 5) -> None:
        self.chain = chain
        self.max_concurrent_requests = max_concurrent_requests
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
            self._semaphore = asyncio.Semaphore(self.max_concurrent_requests)
        return self._semaphore

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
        max_retries: int = 3,
        base_delay: float = 0.5
    ) -> Optional[Dict[str, Any]]:
        """
        Execute an HTTP request with rate-limiting semaphore and exponential backoff retry.
        """
        client = await self.get_client()

        for attempt in range(1, max_retries + 1):
            async with self.get_semaphore():
                try:
                    response = await client.request(
                        method=method,
                        url=url,
                        params=params,
                        headers=headers,
                        json=json_data
                    )
                    if response.status_code == 200:
                        return response.json()
                    elif response.status_code == 429:  # Rate limited
                        backoff = base_delay * (2 ** (attempt - 1))
                        logger.warning(
                            "Rate limited by %s. Backing off for %.2fs (attempt %d/%d)",
                            self.chain.value, backoff, attempt, max_retries
                        )
                        await asyncio.sleep(backoff)
                    else:
                        logger.warning(
                            "HTTP %d from %s API: %s",
                            response.status_code, self.chain.value, response.text[:200]
                        )
                        if attempt == max_retries:
                            return None
                        await asyncio.sleep(base_delay * attempt)
                except httpx.RequestError as exc:
                    logger.warning(
                        "Network error querying %s API (%s): %s. Attempt %d/%d",
                        self.chain.value, url, exc, attempt, max_retries
                    )
                    if attempt == max_retries:
                        return None
                    await asyncio.sleep(base_delay * attempt)

        return None

    @abstractmethod
    async def get_transfers(
        self,
        address: str,
        contract_address: Optional[str] = None,
        limit: int = 50,
        start_timestamp: Optional[int] = None
    ) -> List[Transfer]:
        """
        Fetch incoming and outgoing token and native transfers for a given address.

        :param address: Wallet address to inspect.
        :param contract_address: Optional smart contract filter (e.g. USDT).
        :param limit: Maximum number of transactions to retrieve.
        :param start_timestamp: Earliest unix timestamp filter.
        :return: List of unified Transfer models.
        """
        pass

    @abstractmethod
    async def get_balance(self, address: str) -> WalletBalance:
        """
        Fetch native and common token balances for an address.

        :param address: Target wallet address.
        :return: Unified WalletBalance model.
        """
        pass

    @abstractmethod
    async def get_tx_details(self, tx_hash: str) -> Optional[TxInfo]:
        """
        Fetch full details of a specific transaction.

        :param tx_hash: Transaction identifier hash.
        :return: Unified TxInfo model or None.
        """
        pass

    @abstractmethod
    async def validate_address(self, address: str) -> bool:
        """
        Verify if address is syntactically valid for this blockchain network.
        """
        pass
