"""
Unified dataclass and enum models for blockchain transactions, token transfers,
and wallet info across Tron, Ethereum, and Solana.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any, Union


class Chain(str, Enum):
    """Supported blockchain ecosystems."""
    TRON = "TRON"
    ETHEREUM = "ETHEREUM"
    SOLANA = "SOLANA"

    @classmethod
    def _missing_(cls, value: object):
        if isinstance(value, str):
            val_upper = value.upper().strip()
            for member in cls:
                if member.value == val_upper or member.name == val_upper:
                    return member
        return None

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            return self.value.upper() == other.upper()
        if isinstance(other, Enum):
            return self.name.upper() == other.name.upper()
        return super().__eq__(other)

    def __hash__(self) -> int:
        return hash(self.value.upper())


class TokenType(str, Enum):
    """Token standard types supported across networks."""
    NATIVE = "NATIVE"
    ERC20 = "ERC20"
    TRC20 = "TRC20"
    SPL = "SPL"

    @classmethod
    def _missing_(cls, value: object):
        if isinstance(value, str):
            val_upper = value.upper().strip()
            for member in cls:
                if member.value == val_upper or member.name == val_upper:
                    return member
        return None

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            return self.value.upper() == other.upper()
        if isinstance(other, Enum):
            return self.name.upper() == other.name.upper()
        return super().__eq__(other)

    def __hash__(self) -> int:
        return hash(self.value.upper())


@dataclass
class Transfer:
    """
    Unified model representing a single cryptocurrency or token transfer
    across any supported blockchain network.
    """
    chain: Chain
    tx_hash: str
    from_address: str
    to_address: str
    token: str = "USDT"
    token_contract: Optional[str] = None
    value_raw: Union[int, str] = 0
    value_decimal: float = 0.0
    value_usd: Optional[float] = None
    timestamp: int = 0
    block_number: Optional[int] = None
    fee: Optional[float] = None
    status: str = "SUCCESS"

    def __init__(
        self,
        chain: Any = Chain.TRON,
        tx_hash: str = "",
        from_address: str = "",
        to_address: str = "",
        token: Optional[str] = None,
        token_contract: Optional[str] = None,
        value_raw: Union[int, str] = 0,
        value_decimal: Optional[float] = None,
        value_usd: Optional[float] = None,
        timestamp: int = 0,
        block_number: Optional[int] = None,
        fee: Optional[float] = None,
        status: str = "SUCCESS",
        # Backward compatibility keyword arguments:
        amount: Optional[float] = None,
        token_symbol: Optional[str] = None,
        contract_address: Optional[str] = None,
        raw_amount: Optional[Union[int, str]] = None,
        **kwargs: Any
    ):
        if isinstance(chain, str):
            resolved = Chain(chain)
            self.chain = resolved if resolved is not None else Chain.TRON
        elif isinstance(chain, Enum):
            # Handles ChainType from chains.py or Chain
            resolved = Chain(chain.name)
            self.chain = resolved if resolved is not None else Chain.TRON
        else:
            self.chain = chain

        self.tx_hash = tx_hash
        self.from_address = from_address
        self.to_address = to_address
        self.token = token or token_symbol or "USDT"
        self.token_contract = token_contract or contract_address
        self.value_raw = value_raw if value_raw != 0 else (raw_amount if raw_amount is not None else 0)

        if value_decimal is not None:
            self.value_decimal = float(value_decimal)
        elif amount is not None:
            self.value_decimal = float(amount)
        else:
            self.value_decimal = 0.0

        self.value_usd = value_usd
        self.timestamp = timestamp
        self.block_number = block_number
        self.fee = fee
        self.status = status

    @property
    def amount(self) -> float:
        """Alias for value_decimal for backward compatibility with tracer engine."""
        return self.value_decimal

    @amount.setter
    def amount(self, val: float) -> None:
        self.value_decimal = float(val)

    @property
    def token_symbol(self) -> str:
        """Alias for token for backward compatibility."""
        return self.token

    @token_symbol.setter
    def token_symbol(self, val: str) -> None:
        self.token = val

    @property
    def contract_address(self) -> Optional[str]:
        """Alias for token_contract for backward compatibility."""
        return self.token_contract

    @contract_address.setter
    def contract_address(self, val: Optional[str]) -> None:
        self.token_contract = val

    @property
    def raw_amount(self) -> Optional[str]:
        """Alias for value_raw as string."""
        return str(self.value_raw) if self.value_raw is not None else None


@dataclass
class WalletInfo:
    """
    Aggregated native balance, token balances, and activity profile for an address.
    """
    address: str
    chain: Chain
    balance: float = 0.0
    first_seen: Optional[int] = None
    tx_count: int = 0
    token_balances: Dict[str, float] = field(default_factory=dict)
    total_usd_value: Optional[float] = None
    last_active_timestamp: Optional[int] = None

    def __init__(
        self,
        address: str,
        chain: Any = Chain.TRON,
        balance: float = 0.0,
        first_seen: Optional[int] = None,
        tx_count: int = 0,
        token_balances: Optional[Dict[str, float]] = None,
        total_usd_value: Optional[float] = None,
        last_active_timestamp: Optional[int] = None,
        # Backward compatibility args:
        native_balance: Optional[float] = None,
        native_symbol: Optional[str] = None,
        **kwargs: Any
    ):
        self.address = address
        if isinstance(chain, str):
            resolved = Chain(chain)
            self.chain = resolved if resolved is not None else Chain.TRON
        elif isinstance(chain, Enum):
            resolved = Chain(chain.name)
            self.chain = resolved if resolved is not None else Chain.TRON
        else:
            self.chain = chain

        self.balance = balance if balance != 0.0 else (native_balance if native_balance is not None else 0.0)
        self.first_seen = first_seen
        self.tx_count = tx_count
        self.token_balances = token_balances if token_balances is not None else {}
        self.total_usd_value = total_usd_value
        self.last_active_timestamp = last_active_timestamp

    @property
    def native_balance(self) -> float:
        """Alias for balance."""
        return self.balance

    @native_balance.setter
    def native_balance(self, val: float) -> None:
        self.balance = float(val)

    @property
    def native_symbol(self) -> str:
        """Return native ticker symbol based on chain."""
        if self.chain == Chain.TRON:
            return "TRX"
        elif self.chain == Chain.ETHEREUM:
            return "ETH"
        elif self.chain == Chain.SOLANA:
            return "SOL"
        return "NATIVE"


# Backward compatibility alias
WalletBalance = WalletInfo


@dataclass
class TxInfo:
    """Detailed transaction metadata and embedded token transfers."""
    tx_hash: str
    chain: Chain = Chain.TRON
    block_number: Optional[int] = None
    timestamp: int = 0
    from_address: str = ""
    to_address: Optional[str] = None
    value: float = 0.0
    fee: Optional[float] = None
    status: str = "SUCCESS"
    transfers: List[Transfer] = field(default_factory=list)
    raw_data: Optional[Dict[str, Any]] = None
