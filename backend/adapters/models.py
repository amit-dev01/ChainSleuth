"""
Unified Pydantic v2 data models for blockchain transactions, token transfers,
and wallet balances across Tron, Ethereum, and Solana.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from backend.config.chains import ChainType


class Transfer(BaseModel):
    """Unified model representing a single cryptocurrency or token transfer."""
    tx_hash: str = Field(..., description="Unique transaction hash on the blockchain")
    from_address: str = Field(..., description="Origin wallet or contract address")
    to_address: str = Field(..., description="Destination wallet or contract address")
    amount: float = Field(..., description="Normalized transfer amount (adjusted for decimals)")
    raw_amount: Optional[str] = Field(None, description="Raw integer amount from the blockchain log")
    token_symbol: str = Field(default="USDT", description="Symbol of the transferred asset (e.g. USDT, TRX, ETH)")
    contract_address: Optional[str] = Field(None, description="Smart contract or SPL token mint address")
    timestamp: int = Field(..., description="Unix timestamp of the block in seconds")
    block_number: Optional[int] = Field(None, description="Block height where transaction was confirmed")
    fee: Optional[float] = Field(None, description="Network fee paid for transaction in native currency")
    chain: ChainType = Field(..., description="Blockchain network (tron, ethereum, solana)")
    status: str = Field(default="SUCCESS", description="Execution status of transaction")

    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)


class TxInfo(BaseModel):
    """Detailed transaction metadata and embedded token transfers."""
    tx_hash: str
    chain: ChainType
    block_number: Optional[int] = None
    timestamp: int
    from_address: str
    to_address: Optional[str] = None
    value: float = 0.0
    fee: Optional[float] = None
    status: str = "SUCCESS"
    transfers: List[Transfer] = Field(default_factory=list)
    raw_data: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(populate_by_name=True)


class WalletBalance(BaseModel):
    """Aggregated native and token balances for an address."""
    address: str
    chain: ChainType
    native_balance: float = 0.0
    native_symbol: str = "TRX"
    token_balances: Dict[str, float] = Field(default_factory=dict)
    total_usd_value: Optional[float] = None
    last_active_timestamp: Optional[int] = None

    model_config = ConfigDict(populate_by_name=True)
