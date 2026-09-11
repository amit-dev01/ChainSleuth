"""
Unit and integration tests for BFS Tracing Engine and Obfuscation Detectors.
"""

import pytest
from backend.adapters.models import Transfer
from backend.config.chains import ChainType
from backend.tracer.engine import tracer_engine
from backend.tracer.filters import TraceFilter
from backend.tracer.obfuscation import ObfuscationDetector
from backend.tracer.result import TraceResult


@pytest.mark.asyncio
async def test_bfs_trace_execution():
    """Verify that BFS engine successfully discovers terminal VASP destinations."""
    seed_address = "TMuleWallet88910238128381928312783912"

    result = await tracer_engine.run_trace(
        seed_address=seed_address,
        chain=ChainType.TRON,
        max_hops=4,
        min_amount_usd=10.0
    )

    assert isinstance(result, TraceResult)
    assert result.seed_address == seed_address
    assert result.chain == ChainType.TRON
    assert result.total_stolen_amount > 0.0
    assert len(result.nodes) > 0
    assert len(result.edges) > 0
    assert result.duration_seconds >= 0.0

    # Ensure at least one terminal VASP or path was evaluated
    assert isinstance(result.destination_vasps, list)
    assert len(result.destination_vasps) > 0
    assert any(v["vasp_name"] == "Binance" for v in result.destination_vasps)


def test_trace_filter_rules():
    """Verify dust and zero-value transaction pruning."""
    filter_obj = TraceFilter(min_amount_usd=50.0, max_branches_per_node=2)
    current_wallet = "TWalletCurrent111111111111111111111"

    sample_txs = [
        Transfer(
            tx_hash="tx_zero",
            from_address=current_wallet,
            to_address="TTargetA22222222222222222222222222",
            amount=0.0,  # Zero-value poisoning scam
            token_symbol="USDT",
            timestamp=1000,
            chain=ChainType.TRON
        ),
        Transfer(
            tx_hash="tx_dust",
            from_address=current_wallet,
            to_address="TTargetB33333333333333333333333333",
            amount=5.0,  # Below $50 dust threshold
            token_symbol="USDT",
            timestamp=1000,
            chain=ChainType.TRON
        ),
        Transfer(
            tx_hash="tx_valid_1",
            from_address=current_wallet,
            to_address="TTargetC44444444444444444444444444",
            amount=1500.0,
            token_symbol="USDT",
            timestamp=1000,
            chain=ChainType.TRON
        ),
        Transfer(
            tx_hash="tx_valid_2",
            from_address=current_wallet,
            to_address="TTargetD55555555555555555555555555",
            amount=500.0,
            token_symbol="USDT",
            timestamp=1000,
            chain=ChainType.TRON
        ),
        Transfer(
            tx_hash="tx_valid_3",
            from_address=current_wallet,
            to_address="TTargetE66666666666666666666666666",
            amount=200.0,  # Exceeds max branches (2)
            token_symbol="USDT",
            timestamp=1000,
            chain=ChainType.TRON
        ),
    ]

    filtered = filter_obj.filter_transfers(sample_txs, current_wallet, visited_addresses=set())

    # Only top 2 largest valid transactions should pass
    assert len(filtered) == 2
    assert filtered[0].amount == 1500.0
    assert filtered[1].amount == 500.0


def test_obfuscation_detector_peeling():
    """Verify detection of peeling chain pattern."""
    outflows = [
        Transfer(
            tx_hash="tx1",
            from_address="TSource",
            to_address="TPeeled",
            amount=200.0,  # 20% peeled
            token_symbol="USDT",
            timestamp=1000,
            chain=ChainType.TRON
        ),
        Transfer(
            tx_hash="tx2",
            from_address="TSource",
            to_address="TChangeRemainder",
            amount=800.0,  # 80% remainder forwarded
            token_symbol="USDT",
            timestamp=1000,
            chain=ChainType.TRON
        )
    ]

    peeling = ObfuscationDetector.detect_peeling_chain(outflows)
    assert peeling is not None
    assert peeling["type"] == "PEELING_CHAIN"
    assert peeling["peeled_amount"] == 200.0
    assert peeling["remainder_amount"] == 800.0
