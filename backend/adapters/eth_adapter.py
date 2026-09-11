"""
Ethereum blockchain adapter supporting Etherscan API.
Traces ERC-20 USDT/USDC and native ETH flows to identify exchange deposits.
"""

import logging
import time
from typing import List, Optional, Dict, Any

from backend.adapters.base import BaseAdapter
from backend.adapters.models import Transfer, TxInfo, WalletBalance
from backend.config.chains import ChainType, TOKEN_CONTRACTS, CHAIN_ADDRESS_REGEX
from backend.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

ETH_USDT_CONTRACT = TOKEN_CONTRACTS[ChainType.ETHEREUM]["USDT"]["address"]


class EthereumAdapter(BaseAdapter):
    """Adapter for querying Etherscan ERC-20 and native ETH transfers."""

    def __init__(self) -> None:
        super().__init__(chain=ChainType.ETHEREUM, max_concurrent_requests=5)
        self.api_url = settings.ETHERSCAN_API_URL
        self.api_key = settings.ETHERSCAN_API_KEY

    async def validate_address(self, address: str) -> bool:
        """Validate Ethereum hex address pattern."""
        return bool(CHAIN_ADDRESS_REGEX[ChainType.ETHEREUM].match(address.strip()))

    async def get_transfers(
        self,
        address: str,
        contract_address: Optional[str] = None,
        limit: int = 50,
        start_timestamp: Optional[int] = None
    ) -> List[Transfer]:
        """
        Fetch ERC-20 token transfers (defaulting to USDT) for an Ethereum address.
        """
        contract = contract_address or ETH_USDT_CONTRACT
        params: Dict[str, Any] = {
            "module": "account",
            "action": "tokentx",
            "address": address,
            "contractaddress": contract,
            "page": 1,
            "offset": min(limit, 100),
            "sort": "desc",
        }
        if self.api_key:
            params["apikey"] = self.api_key

        data = await self._request_with_retry(
            method="GET",
            url=self.api_url,
            params=params
        )

        transfers: List[Transfer] = []
        if data and data.get("status") == "1" and isinstance(data.get("result"), list):
            for item in data["result"]:
                try:
                    decimals = int(item.get("tokenDecimal", 6))
                    raw_val = str(item.get("value", "0"))
                    amount = float(raw_val) / (10 ** decimals)
                    ts = int(item.get("timeStamp", 0))

                    if start_timestamp and ts < start_timestamp:
                        continue

                    transfers.append(
                        Transfer(
                            tx_hash=item.get("hash", ""),
                            from_address=item.get("from", ""),
                            to_address=item.get("to", ""),
                            amount=amount,
                            raw_amount=raw_val,
                            token_symbol=item.get("tokenSymbol", "USDT"),
                            contract_address=item.get("contractAddress", contract),
                            timestamp=ts,
                            block_number=int(item.get("blockNumber", 0)),
                            fee=(float(item.get("gasPrice", 0)) * float(item.get("gasUsed", 0))) / 1e18,
                            chain=ChainType.ETHEREUM,
                            status="SUCCESS"
                        )
                    )
                except Exception as exc:
                    logger.debug("Failed parsing Ethereum transfer item: %s", exc)

        # Offline / Demo Fallback
        if not transfers and not self.api_key:
            logger.info("Using simulated data for Ethereum address %s (demo mode)", address)
            transfers = self._generate_mock_transfers(address)

        return transfers

    async def get_balance(self, address: str) -> WalletBalance:
        """Fetch native ETH balance for Ethereum address."""
        params: Dict[str, Any] = {
            "module": "account",
            "action": "balance",
            "address": address,
            "tag": "latest"
        }
        if self.api_key:
            params["apikey"] = self.api_key

        data = await self._request_with_retry(method="GET", url=self.api_url, params=params)
        native_balance = 0.0
        if data and data.get("status") == "1":
            native_balance = float(data.get("result", 0)) / 1e18

        return WalletBalance(
            address=address,
            chain=ChainType.ETHEREUM,
            native_balance=native_balance,
            native_symbol="ETH",
            token_balances={"USDT": 0.0},
            total_usd_value=native_balance * 3200.0
        )

    async def get_tx_details(self, tx_hash: str) -> Optional[TxInfo]:
        """Fetch transaction receipt from Etherscan."""
        params: Dict[str, Any] = {
            "module": "proxy",
            "action": "eth_getTransactionByHash",
            "txhash": tx_hash
        }
        if self.api_key:
            params["apikey"] = self.api_key

        data = await self._request_with_retry(method="GET", url=self.api_url, params=params)
        if not data or "result" not in data or not data["result"]:
            return None

        res = data["result"]
        return TxInfo(
            tx_hash=tx_hash,
            chain=ChainType.ETHEREUM,
            timestamp=int(time.time()),
            from_address=res.get("from", ""),
            to_address=res.get("to"),
            value=int(res.get("value", "0x0"), 16) / 1e18,
            status="SUCCESS",
            raw_data=res
        )

    def _generate_mock_transfers(self, address: str) -> List[Transfer]:
        """Generate demo transfers on Ethereum network."""
        now = int(time.time())
        binance_eth_hot = "0x28C6c06298d514Db089934071355E5743bf21d60"
        return [
            Transfer(
                tx_hash=f"0xeth_tx_in_{abs(hash(address)) % 1000000}",
                from_address="0x1234567890123456789012345678901234567890",
                to_address=address,
                amount=12000.0,
                raw_amount="12000000000",
                token_symbol="USDT",
                contract_address=ETH_USDT_CONTRACT,
                timestamp=now - 5000,
                block_number=19800000,
                chain=ChainType.ETHEREUM,
                status="SUCCESS"
            ),
            Transfer(
                tx_hash=f"0xeth_tx_out_{abs(hash(address)) % 1000000}",
                from_address=address,
                to_address=binance_eth_hot,
                amount=11950.0,
                raw_amount="11950000000",
                token_symbol="USDT",
                contract_address=ETH_USDT_CONTRACT,
                timestamp=now - 2500,
                block_number=19800150,
                chain=ChainType.ETHEREUM,
                status="SUCCESS"
            )
        ]
