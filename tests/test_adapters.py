"""
Unit and integration tests for unified blockchain adapters (Tron, Ethereum, Solana).
Includes real network tests against TronGrid for known exchange hot wallets.
"""

import asyncio
import pytest
from backend.adapters.models import Transfer, WalletInfo, WalletBalance, Chain, TokenType
from backend.adapters.base import BlockchainAdapter, RateLimiter, retry_with_backoff, get_adapter
from backend.adapters.tron_adapter import TronAdapter
from backend.adapters.eth_adapter import EthereumAdapter
from backend.adapters.solana_adapter import SolanaAdapter
from backend.config.chains import detect_chain, ChainType


def test_models_and_dataclasses():
    """Verify @dataclass Transfer, WalletInfo, Chain, and TokenType enums."""
    tx = Transfer(
        chain=Chain.TRON,
        tx_hash="0xabc123",
        from_address="TFrom11111111111111111111111111111",
        to_address="TTo222222222222222222222222222222",
        token="USDT",
        token_contract="TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",
        value_raw="1000000",
        value_decimal=1.0,
        value_usd=1.0,
        timestamp=1700000000,
        block_number=50000000
    )

    # Test field types and values
    assert tx.chain == Chain.TRON
    assert tx.tx_hash == "0xabc123"
    assert tx.from_address == "TFrom11111111111111111111111111111"
    assert tx.to_address == "TTo222222222222222222222222222222"
    assert tx.token == "USDT"
    assert tx.token_contract == "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
    assert tx.value_raw == "1000000"
    assert tx.value_decimal == 1.0
    assert tx.value_usd == 1.0
    assert tx.timestamp == 1700000000
    assert tx.block_number == 50000000

    # Test backward compatibility properties
    assert tx.amount == 1.0
    assert tx.token_symbol == "USDT"
    assert tx.contract_address == "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
    assert tx.raw_amount == "1000000"

    # Test WalletInfo
    winfo = WalletInfo(
        address="TFrom11111111111111111111111111111",
        chain=Chain.TRON,
        balance=150.5,
        first_seen=1600000000,
        tx_count=25,
        token_balances={"USDT": 500.0}
    )
    assert winfo.address == "TFrom11111111111111111111111111111"
    assert winfo.chain == Chain.TRON
    assert winfo.balance == 150.5
    assert winfo.native_balance == 150.5
    assert winfo.native_symbol == "TRX"
    assert winfo.first_seen == 1600000000
    assert winfo.tx_count == 25
    assert winfo.token_balances["USDT"] == 500.0

    # Test TokenType enum
    assert TokenType.NATIVE == "NATIVE"
    assert TokenType.ERC20 == "ERC20"
    assert TokenType.TRC20 == "TRC20"
    assert TokenType.SPL == "SPL"


@pytest.mark.asyncio
async def test_rate_limiter_and_retry():
    """Verify RateLimiter token bucket behavior and retry_with_backoff decorator."""
    limiter = RateLimiter(tokens_per_second=20.0, max_tokens=5.0)
    await limiter.acquire(1.0)
    assert limiter.tokens < 5.0

    attempts = 0

    @retry_with_backoff(max_retries=3, base_delay=0.01, backoff_factor=1.5, retryable_exceptions=(ValueError,))
    async def flaky_fn():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise ValueError("Transient error")
        return "success"

    result = await flaky_fn()
    assert result == "success"
    assert attempts == 3


def test_adapter_factory():
    """Verify get_adapter factory returns correct BlockchainAdapter instances."""
    tron_adapter = get_adapter(Chain.TRON)
    eth_adapter = get_adapter(Chain.ETHEREUM)
    sol_adapter = get_adapter(Chain.SOLANA)

    assert isinstance(tron_adapter, TronAdapter)
    assert isinstance(eth_adapter, EthereumAdapter)
    assert isinstance(sol_adapter, SolanaAdapter)

    # String input support
    assert isinstance(get_adapter("tron"), TronAdapter)
    assert isinstance(get_adapter("ethereum"), EthereumAdapter)
    assert isinstance(get_adapter("solana"), SolanaAdapter)


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
async def test_tron_adapter_real_known_address():
    """
    Test Tron adapter with a real known address (Binance Tron hot wallet: TNaRAoLUyYEV2uF7GUrzSjRQTU8v5ZJ5VR).
    Validates outgoing, incoming, token transfers, balances, and first_seen against TronGrid.
    """
    adapter = TronAdapter()
    binance_tron_hot = "TNaRAoLUyYEV2uF7GUrzSjRQTU8v5ZJ5VR"

    is_valid = await adapter.validate_address(binance_tron_hot)
    assert is_valid is True

    # 1. Test get_outgoing_transfers
    out_transfers = await adapter.get_outgoing_transfers(binance_tron_hot, limit=5)
    assert isinstance(out_transfers, list)
    assert len(out_transfers) > 0
    first_out = out_transfers[0]
    assert isinstance(first_out, Transfer)
    assert first_out.chain == Chain.TRON
    assert first_out.token == "USDT"
    assert first_out.value_decimal > 0.0
    assert first_out.from_address.lower() == binance_tron_hot.lower()
    assert first_out.tx_hash != ""

    # 2. Test get_incoming_transfers
    in_transfers = await adapter.get_incoming_transfers(binance_tron_hot, limit=5)
    assert isinstance(in_transfers, list)
    assert len(in_transfers) > 0
    first_in = in_transfers[0]
    assert isinstance(first_in, Transfer)
    assert first_in.chain == Chain.TRON
    assert first_in.to_address.lower() == binance_tron_hot.lower()

    # 3. Test get_balance
    wallet_info = await adapter.get_balance(binance_tron_hot)
    assert isinstance(wallet_info, WalletInfo)
    assert wallet_info.chain == Chain.TRON
    assert wallet_info.balance > 0.0  # Binance hot wallet has TRX balance
    assert isinstance(wallet_info.token_balances, dict)

    # 4. Test get_first_seen
    first_seen = await adapter.get_first_seen(binance_tron_hot)
    assert isinstance(first_seen, int)
    assert first_seen > 0

    # 5. Test get_token_transfers
    token_txs = await adapter.get_token_transfers(binance_tron_hot, limit=3)
    assert isinstance(token_txs, list)
    assert len(token_txs) > 0

    await adapter.close()


@pytest.mark.asyncio
async def test_tron_adapter_error_handling_invalid_address():
    """
    Test Tron adapter error handling when querying with an invalid checksum address
    (e.g., TKbXbRRsmLgDmBHRRwqMFagAjZhyZNMPax).
    TronGrid returns 400 'A valid account address is required.', which adapter
    must catch and handle cleanly without unhandled exceptions.
    """
    adapter = TronAdapter()
    invalid_addr = "TKbXbRRsmLgDmBHRRwqMFagAjZhyZNMPax"

    # Validate address format regex vs checksum
    valid_regex = await adapter.validate_address(invalid_addr)
    assert valid_regex is True  # Matches Tron length/prefix regex

    # Adapter catches 400 from TronGrid and returns empty list or fallback
    transfers = await adapter.get_outgoing_transfers(invalid_addr, limit=5)
    assert isinstance(transfers, list)

    balance = await adapter.get_balance(invalid_addr)
    assert isinstance(balance, WalletInfo)
    assert balance.address == invalid_addr

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
    assert first_tx.chain == Chain.ETHEREUM
    assert first_tx.amount > 0.0

    # Test outgoing / incoming methods
    outgoing = await adapter.get_outgoing_transfers(test_addr, limit=5)
    assert isinstance(outgoing, list)

    incoming = await adapter.get_incoming_transfers(test_addr, limit=5)
    assert isinstance(incoming, list)

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
    assert first_tx.chain == Chain.SOLANA
    assert first_tx.amount > 0.0

    # Test outgoing / incoming methods
    outgoing = await adapter.get_outgoing_transfers(test_addr, limit=5)
    assert isinstance(outgoing, list)

    incoming = await adapter.get_incoming_transfers(test_addr, limit=5)
    assert isinstance(incoming, list)

    await adapter.close()


@pytest.mark.asyncio
async def test_wallet_balance():
    """Verify adapter balance retrieval models."""
    adapter = TronAdapter()
    balance = await adapter.get_balance("TNaRAoLUyYEV2uF7GUrzSjRQTU8v5ZJ5VR")

    assert isinstance(balance, WalletBalance)
    assert balance.chain == Chain.TRON
    assert balance.native_symbol == "TRX"
    assert isinstance(balance.token_balances, dict)

    await adapter.close()
