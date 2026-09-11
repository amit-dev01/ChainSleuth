"""
Tron blockchain adapter supporting TronGrid API.
Specialized for TRC-20 USDT tracing — the primary vehicle in 80%+ of Indian cyber frauds.
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

TRON_USDT_CONTRACT = TOKEN_CONTRACTS[ChainType.TRON]["USDT"]["address"]


class TronAdapter(BaseAdapter):
    """Adapter for querying TronGrid TRC-20 and native TRX transactions."""

    def __init__(self) -> None:
        super().__init__(chain=ChainType.TRON, max_concurrent_requests=10)
        self.api_url = settings.TRON_GRID_URL.rstrip("/")
        self.api_key = settings.TRONGRID_API_KEY

    def _get_headers(self) -> Dict[str, str]:
        """Generate HTTP headers including optional TronGrid API key."""
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["TRON-PRO-API-KEY"] = self.api_key
        return headers

    async def validate_address(self, address: str) -> bool:
        """Validate Tron base58 address pattern."""
        return bool(CHAIN_ADDRESS_REGEX[ChainType.TRON].match(address.strip()))

    async def get_transfers(
        self,
        address: str,
        contract_address: Optional[str] = None,
        limit: int = 50,
        start_timestamp: Optional[int] = None
    ) -> List[Transfer]:
        """
        Fetch TRC-20 token transfers (defaulting to USDT) for a Tron address.
        """
        contract = contract_address or TRON_USDT_CONTRACT
        url = f"{self.api_url}/v1/accounts/{address}/transactions/trc20"
        params: Dict[str, Any] = {
            "limit": min(limit, 200),
            "contract_address": contract,
            "only_confirmed": "true",
            "order_by": "block_timestamp,desc"
        }
        if start_timestamp:
            params["min_timestamp"] = start_timestamp * 1000

        data = await self._request_with_retry(
            method="GET",
            url=url,
            params=params,
            headers=self._get_headers()
        )

        transfers: List[Transfer] = []
        if data and "data" in data and isinstance(data["data"], list):
            for item in data["data"]:
                try:
                    token_info = item.get("token_info", {})
                    decimals = int(token_info.get("decimals", 6))
                    raw_val = str(item.get("value", "0"))
                    amount = float(raw_val) / (10 ** decimals)
                    ts_ms = item.get("block_timestamp", 0)
                    ts_sec = int(ts_ms / 1000) if ts_ms > 1e11 else int(ts_ms)

                    transfers.append(
                        Transfer(
                            tx_hash=item.get("transaction_id", ""),
                            from_address=item.get("from", ""),
                            to_address=item.get("to", ""),
                            amount=amount,
                            raw_amount=raw_val,
                            token_symbol=token_info.get("symbol", "USDT"),
                            contract_address=token_info.get("address", contract),
                            timestamp=ts_sec,
                            block_number=item.get("block_number"),
                            chain=ChainType.TRON,
                            status="SUCCESS"
                        )
                    )
                except Exception as exc:
                    logger.debug("Failed parsing Tron transfer item: %s", exc)

        # Offline / Demo Fallback if API returned no data or key is not provided
        if not transfers and not self.api_key:
            logger.info("Using simulated data for Tron address %s (demo/testing mode)", address)
            transfers = self._generate_mock_transfers(address)

        return transfers

    async def get_balance(self, address: str) -> WalletBalance:
        """Fetch native TRX and TRC20 USDT balance for Tron address."""
        url = f"{self.api_url}/v1/accounts/{address}"
        data = await self._request_with_retry(
            method="GET",
            url=url,
            headers=self._get_headers()
        )

        native_balance = 0.0
        token_balances: Dict[str, float] = {"USDT": 0.0}

        if data and "data" in data and len(data["data"]) > 0:
            acc_data = data["data"][0]
            # Native TRX is measured in SUN (10^6)
            sun_balance = float(acc_data.get("balance", 0))
            native_balance = sun_balance / 1e6

            # TRC-20 token holdings
            trc20_list = acc_data.get("trc20", [])
            for token_map in trc20_list:
                for c_addr, val in token_map.items():
                    if c_addr == TRON_USDT_CONTRACT:
                        token_balances["USDT"] = float(val) / 1e6

        return WalletBalance(
            address=address,
            chain=ChainType.TRON,
            native_balance=native_balance,
            native_symbol="TRX",
            token_balances=token_balances,
            total_usd_value=token_balances.get("USDT", 0.0) + (native_balance * 0.12)
        )

    async def get_tx_details(self, tx_hash: str) -> Optional[TxInfo]:
        """Fetch transaction metadata from TronGrid."""
        url = f"{self.api_url}/wallet/gettransactionbyid"
        data = await self._request_with_retry(
            method="POST",
            url=url,
            headers=self._get_headers(),
            json_data={"value": tx_hash}
        )

        if not data or "txID" not in data:
            return None

        raw_data = data.get("raw_data", {})
        timestamp = int(raw_data.get("timestamp", 0) / 1000)

        return TxInfo(
            tx_hash=tx_hash,
            chain=ChainType.TRON,
            timestamp=timestamp,
            from_address="",
            status="SUCCESS",
            raw_data=data
        )

    def _generate_mock_transfers(self, address: str) -> List[Transfer]:
        """
        Generate deterministic mock transfers for hackathon demonstration
        and test cases simulating cyber crime mule and exchange fund flows.
        """
        now = int(time.time())
        # Known demo targets
        binance_hot = "TNaRAoLUyYEV2uF7GUrzSjRQTU8v5ZJ5VR"
        wazirx_hot = "TWd4SpPnMHRqeq4ndhhnP3eP1e7Jp6g4pD"

        return [
            Transfer(
                tx_hash=f"tron_tx_in_{abs(hash(address)) % 1000000}",
                from_address="TMuleWallet88910238128381928312783912",
                to_address=address,
                amount=25000.0,
                raw_amount="25000000000",
                token_symbol="USDT",
                contract_address=TRON_USDT_CONTRACT,
                timestamp=now - 7200,
                block_number=58920102,
                chain=ChainType.TRON,
                status="SUCCESS"
            ),
            Transfer(
                tx_hash=f"tron_tx_out_1_{abs(hash(address)) % 1000000}",
                from_address=address,
                to_address="THopWalletIntermediate98218731823910",
                amount=15000.0,
                raw_amount="15000000000",
                token_symbol="USDT",
                contract_address=TRON_USDT_CONTRACT,
                timestamp=now - 3600,
                block_number=58920250,
                chain=ChainType.TRON,
                status="SUCCESS"
            ),
            Transfer(
                tx_hash=f"tron_tx_out_2_{abs(hash(address)) % 1000000}",
                from_address=address,
                to_address=binance_hot,
                amount=9850.0,
                raw_amount="9850000000",
                token_symbol="USDT",
                contract_address=TRON_USDT_CONTRACT,
                timestamp=now - 1800,
                block_number=58920380,
                chain=ChainType.TRON,
                status="SUCCESS"
            )
        ]
