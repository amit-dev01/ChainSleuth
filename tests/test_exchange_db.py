"""
Unit and integration tests for Exchange/VASP Attribution Database and Clustering Heuristics.
"""

import pytest
from backend.adapters.models import Transfer
from backend.config.chains import ChainType
from backend.exchange_db.cluster import WalletClusterEngine
from backend.exchange_db.service import exchange_service


@pytest.mark.asyncio
async def test_identify_known_exchanges():
    """Verify attribution for Binance, WazirX, and Tornado Cash."""
    # Binance Tron Hot Wallet
    binance_tron = "TNaRAoLUyYEV2uF7GUrzSjRQTU8v5ZJ5VR"
    res1 = await exchange_service.identify_address(binance_tron, "tron")
    assert res1 is not None
    assert res1["name"] == "Binance"
    assert res1["entity_type"] == "CEX"
    assert exchange_service.is_terminal_vasp(res1) is True

    # WazirX India VASP
    wazirx_tron = "TWd4SpPnMHRqeq4ndhhnP3eP1e7Jp6g4pD"
    res2 = await exchange_service.identify_address(wazirx_tron, "tron")
    assert res2 is not None
    assert res2["name"] == "WazirX"
    assert res2["fiu_registered"] is True

    # Tornado Cash Ethereum Mixer
    tornado_eth = "0xd90e2f925DA726b50C4Ed8D0Fb90Ad053324F31b"
    res3 = await exchange_service.identify_address(tornado_eth, "ethereum")
    assert res3 is not None
    assert "Tornado Cash" in res3["name"]
    assert res3["entity_type"] == "MIXER"


@pytest.mark.asyncio
async def test_custom_attribution_registration():
    """Verify dynamic LEA tagging of newly uncovered fraud syndicate hubs."""
    custom_addr = "TCustomSyndicateDepositVault999123"
    await exchange_service.register_attribution(
        address=custom_addr,
        chain="tron",
        name="TaskScam_Mule_Cluster_A",
        entity_type="MULE_NETWORK",
        role="DEPOSIT_COLLECTION",
        fiu_registered=False
    )

    verified = await exchange_service.identify_address(custom_addr, "tron")
    assert verified is not None
    assert verified["name"] == "TaskScam_Mule_Cluster_A"
    assert verified["entity_type"] == "MULE_NETWORK"


def test_deposit_sweep_clustering():
    """Verify rapid sweep clustering heuristic."""
    transfers = [
        Transfer(
            tx_hash="tx_in",
            from_address="TVictim",
            to_address="TMuleA",
            amount=10000.0,
            token_symbol="USDT",
            timestamp=1700000000,
            chain=ChainType.TRON
        ),
        Transfer(
            tx_hash="tx_out",
            from_address="TMuleA",
            to_address="TCentralHub",
            amount=9950.0,  # Swept 99.5% within 10 minutes
            token_symbol="USDT",
            timestamp=1700000600,
            chain=ChainType.TRON
        )
    ]

    sweeps = WalletClusterEngine.identify_deposit_sweeps(transfers)
    assert len(sweeps) == 1
    assert sweeps[0]["type"] == "RAPID_SWEEP"
    assert sweeps[0]["swept_amount"] == 9950.0
    assert sweeps[0]["latency_seconds"] == 600
