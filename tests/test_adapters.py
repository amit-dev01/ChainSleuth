"""
Unit and integration tests for unified blockchain adapters (Tron, Ethereum, Solana).
"""

import pytest
from backend.adapters.models import Transfer, WalletBalance
from backend.adapters.tron_adapter import TronAdapter
from backend.adapters.eth_adapter import EthereumAdapter
from backend.adapters.solana_adapter import SolanaAdapter
from backend.config.chains import detect_chain, ChainType


@pytest.mark.asyncio
async def test_chain_detection():
    """Verify regex heuristics accurately detect Tron, Ethereum, and Solana addresses."""
    tron_addr = "TNaRAoLUyYEV2uF7GUrzSjRQTU8v5ZJ5VR"
    eth_addr = "0x28C6c06298d514Db089934071355E5743bf21d60"
    sol_addr = "5tzFkiKscMRHK5ZXWBraXZHgYTUEYTM3MQNCGfj13bPr"

    assert detect_chain(tron_addr) == ChainType.TRON
    assert detect_chain(eth_addr) == ChainType.ETHEREUM
    assert detect_chain(sol_addr) == ChainType.SOLANA
    assert detect_chain("invalid_address_string") is None


@pytest.mark.asyncio
async def test_tron_adapter_transfers():
    """Verify Tron adapter returns valid unified Transfer objects."""
    adapter = TronAdapter()
    test_addr = "TNaRAoLUyYEV2uF7GUrzSjRQTU8v5ZJ5VR"

    is_valid = await adapter.validate_address(test_addr)
    assert is_valid is True

    transfers = await adapter.get_transfers(test_addr, limit=10)
    assert isinstance(transfers, list)
    assert len(transfers) > 0

    first_tx = transfers[0]
    assert isinstance(first_tx, Transfer)
    assert first_tx.chain == ChainType.TRON
    assert first_tx.token_symbol == "USDT"
    assert first_tx.amount > 0.0
    assert first_tx.tx_hash != ""

    await adapter.close()


@pytest.mark.asyncio
async def test_eth_adapter_transfers():
    """Verify Ethereum adapter returns unified Transfer objects."""
    adapter = EthereumAdapter()
    test_addr = "0x28C6c06298d514Db089934071355E5743bf21d60"

    is_valid = await adapter.validate_address(test_addr)
    assert is_valid is True

    transfers = await adapter.get_transfers(test_addr, limit=10)
    assert isinstance(transfers, list)
    assert len(transfers) > 0

    first_tx = transfers[0]
    assert isinstance(first_tx, Transfer)
    assert first_tx.chain == ChainType.ETHEREUM
    assert first_tx.amount > 0.0

    await adapter.close()


@pytest.mark.asyncio
async def test_solana_adapter_transfers():
    """Verify Solana adapter returns unified Transfer objects."""
    adapter = SolanaAdapter()
    test_addr = "5tzFkiKscMRHK5ZXWBraXZHgYTUEYTM3MQNCGfj13bPr"

    is_valid = await adapter.validate_address(test_addr)
    assert is_valid is True

    transfers = await adapter.get_transfers(test_addr, limit=10)
    assert isinstance(transfers, list)
    assert len(transfers) > 0

    first_tx = transfers[0]
    assert isinstance(first_tx, Transfer)
    assert first_tx.chain == ChainType.SOLANA
    assert first_tx.amount > 0.0

    await adapter.close()


@pytest.mark.asyncio
async def test_wallet_balance():
    """Verify adapter balance retrieval models."""
    adapter = TronAdapter()
    balance = await adapter.get_balance("TNaRAoLUyYEV2uF7GUrzSjRQTU8v5ZJ5VR")

    assert isinstance(balance, WalletBalance)
    assert balance.chain == ChainType.TRON
    assert balance.native_symbol == "TRX"
    assert isinstance(balance.token_balances, dict)

    await adapter.close()
