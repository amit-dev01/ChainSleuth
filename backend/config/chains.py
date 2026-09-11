"""
Chain-specific configurations, RPC URLs, API endpoints, USDT contracts,
block explorer URLs, token mappings, and regex heuristics for automatic chain detection.
"""

from enum import Enum
import re
from typing import Dict, Any, Optional


class ChainType(str, Enum):
    """Supported blockchain ecosystems."""
    TRON = "tron"
    ETHEREUM = "ethereum"
    SOLANA = "solana"


class TokenSymbol(str, Enum):
    """Common tracked tokens in Indian cyber fraud investigations."""
    USDT = "USDT"
    USDC = "USDC"
    TRX = "TRX"
    ETH = "ETH"
    SOL = "SOL"


# Address validation patterns
CHAIN_ADDRESS_REGEX: Dict[ChainType, re.Pattern] = {
    # Tron addresses start with 'T' and are 34 base58 characters
    ChainType.TRON: re.compile(r"^T[1-9A-HJ-NP-za-km-z]{33}$"),
    # Ethereum addresses start with '0x' and are 40 hexadecimal characters
    ChainType.ETHEREUM: re.compile(r"^0x[a-fA-F0-9]{40}$"),
    # Solana addresses are 32 to 44 base58 characters
    ChainType.SOLANA: re.compile(r"^[1-9A-HJ-NP-za-km-z]{32,44}$"),
}

# Chain-specific RPCs, API endpoints, Explorer URLs and USDT contracts
CHAIN_CONFIGS: Dict[ChainType, Dict[str, Any]] = {
    ChainType.TRON: {
        "name": "TRON Network",
        "primary_token": "USDT-TRC20",
        "usdt_contract": "TR7NHqJEKQxGTCi8q8ZY4pL8otSzgjLj6t",
        "api_endpoint": "https://api.trongrid.io",
        "rpc_url": "https://api.trongrid.io",
        "explorer_tx_url": "https://tronscan.org/#/transaction/{tx_hash}",
        "explorer_address_url": "https://tronscan.org/#/address/{address}",
        "is_primary_fraud_chain": True
    },
    ChainType.ETHEREUM: {
        "name": "Ethereum Mainnet",
        "primary_token": "USDT-ERC20",
        "usdt_contract": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
        "api_endpoint": "https://api.etherscan.io/api",
        "rpc_url": "https://cloudflare-eth.com",
        "explorer_tx_url": "https://etherscan.io/tx/{tx_hash}",
        "explorer_address_url": "https://etherscan.io/address/{address}",
        "is_primary_fraud_chain": False
    },
    ChainType.SOLANA: {
        "name": "Solana Mainnet",
        "primary_token": "USDT-SPL",
        "usdt_contract": "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",
        "api_endpoint": "https://api.helius.xyz/v0",
        "rpc_url": "https://mainnet.helius-rpc.com",
        "explorer_tx_url": "https://solscan.io/tx/{tx_hash}",
        "explorer_address_url": "https://solscan.io/account/{address}",
        "is_primary_fraud_chain": False
    }
}

# Known stablecoin and high-value token contract addresses
TOKEN_CONTRACTS: Dict[ChainType, Dict[str, Dict[str, Any]]] = {
    ChainType.TRON: {
        "USDT": {
            "address": "TR7NHqJEKQxGTCi8q8ZY4pL8otSzgjLj6t",
            "decimals": 6,
            "name": "Tether USD (TRC-20)",
        },
        "USDC": {
            "address": "TEkxiTehnzSmSe2XqrBj4w32RUN966rdz8",
            "decimals": 6,
            "name": "USD Coin (TRC-20)",
        },
        "TRX": {
            "address": "native",
            "decimals": 6,
            "name": "TRON Native",
        }
    },
    ChainType.ETHEREUM: {
        "USDT": {
            "address": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
            "decimals": 6,
            "name": "Tether USD (ERC-20)",
        },
        "USDC": {
            "address": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
            "decimals": 6,
            "name": "USD Coin (ERC-20)",
        },
        "ETH": {
            "address": "native",
            "decimals": 18,
            "name": "Ethereum Native",
        }
    },
    ChainType.SOLANA: {
        "USDT": {
            "address": "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",
            "decimals": 6,
            "name": "Tether USD (SPL)",
        },
        "USDC": {
            "address": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
            "decimals": 6,
            "name": "USD Coin (SPL)",
        },
        "SOL": {
            "address": "native",
            "decimals": 9,
            "name": "Solana Native",
        }
    }
}


def detect_chain(address: str) -> Optional[ChainType]:
    """
    Detect the blockchain network for a given wallet address using format heuristics.

    :param address: Cryptocurrency wallet address string.
    :return: Identified ChainType or None if unrecognized.
    """
    cleaned = address.strip()
    if CHAIN_ADDRESS_REGEX[ChainType.TRON].match(cleaned):
        return ChainType.TRON
    if CHAIN_ADDRESS_REGEX[ChainType.ETHEREUM].match(cleaned):
        return ChainType.ETHEREUM
    if CHAIN_ADDRESS_REGEX[ChainType.SOLANA].match(cleaned):
        return ChainType.SOLANA
    return None


def get_token_decimals(chain: ChainType, symbol_or_contract: str) -> int:
    """
    Retrieve token decimal places for proper unit formatting.

    :param chain: Blockchain network.
    :param symbol_or_contract: Token ticker (e.g. 'USDT') or contract address.
    :return: Number of decimals (defaulting to 6 for stablecoins or 18).
    """
    tokens = TOKEN_CONTRACTS.get(chain, {})
    upper_symbol = symbol_or_contract.upper()
    if upper_symbol in tokens:
        return tokens[upper_symbol]["decimals"]

    for meta in tokens.values():
        if meta["address"].lower() == symbol_or_contract.lower():
            return meta["decimals"]

    return 6 if chain in (ChainType.TRON, ChainType.SOLANA) else 18


def get_explorer_tx_url(chain: ChainType, tx_hash: str) -> str:
    """Return clickable block explorer URL for a given transaction."""
    template = CHAIN_CONFIGS[chain]["explorer_tx_url"]
    return template.format(tx_hash=tx_hash)


def get_explorer_address_url(chain: ChainType, address: str) -> str:
    """Return clickable block explorer URL for a given wallet address."""
    template = CHAIN_CONFIGS[chain]["explorer_address_url"]
    return template.format(address=address)
