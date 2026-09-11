"""
Wallet intelligence endpoints for querying balance, transaction histories,
risk scores, and registering suspect addresses for continuous monitoring.
"""

from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.api.middleware.auth import get_current_user
from backend.api.schemas.wallet import WalletOverviewResponse, WalletRiskResponse, WalletMonitorRequest
from backend.config.chains import detect_chain, ChainType
from backend.exchange_db.service import exchange_service
from backend.risk.scorer import risk_scorer
from backend.storage.redis_client import redis_client
from backend.tracer.engine import tracer_engine

router = APIRouter(prefix="/wallet", tags=["Wallet Intelligence"])


@router.get("/{address}", response_model=WalletOverviewResponse)
async def get_wallet_overview(
    address: str,
    chain: str = Query(None, description="Optional chain (tron, ethereum, solana)"),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> WalletOverviewResponse:
    """
    Retrieve wallet balance, token holdings, entity attribution, and risk tier.
    """
    clean_addr = address.strip()
    target_chain = ChainType(chain.lower()) if chain else detect_chain(clean_addr) or ChainType.TRON
    adapter = tracer_engine.get_adapter(target_chain)

    try:
        balance = await adapter.get_balance(clean_addr)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed retrieving balance from {target_chain.value} network."
        )

    entity = await exchange_service.identify_address(clean_addr, target_chain.value)

    # Check monitoring status
    monitored_list = await redis_client.get_json("monitored_wallets") or []
    is_monitored = any(m.get("address", "").lower() == clean_addr.lower() for m in monitored_list)

    return WalletOverviewResponse(
        address=clean_addr,
        chain=target_chain.value,
        label=entity.get("name") if entity else "Unlabeled Wallet",
        entity_name=entity.get("name") if entity else None,
        entity_type=entity.get("entity_type") if entity else "WALLET",
        native_balance=balance.native_balance,
        native_symbol=balance.native_symbol,
        token_balances=balance.token_balances,
        total_usd_value=balance.total_usd_value or 0.0,
        risk_score=90.0 if not entity else 15.0,
        risk_tier="CRITICAL" if not entity and balance.total_usd_value and balance.total_usd_value > 10000 else "LOW",
        is_monitored=is_monitored
    )


@router.get("/{address}/risk", response_model=WalletRiskResponse)
async def get_wallet_risk(
    address: str,
    chain: str = Query(None, description="Blockchain network"),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> WalletRiskResponse:
    """
    Compute comprehensive AML and cyber fraud risk assessment for an address.
    """
    clean_addr = address.strip()
    target_chain = ChainType(chain.lower()) if chain else detect_chain(clean_addr) or ChainType.TRON
    adapter = tracer_engine.get_adapter(target_chain)

    transfers = await adapter.get_transfers(clean_addr, limit=50)
    balance = await adapter.get_balance(clean_addr)

    assessment = risk_scorer.calculate_risk(
        address=clean_addr,
        chain=target_chain.value,
        transfers=transfers,
        balance=balance
    )

    return WalletRiskResponse(
        address=assessment.address,
        chain=assessment.chain,
        risk_score=assessment.risk_score,
        risk_tier=assessment.risk_tier,
        is_suspicious=assessment.is_suspicious,
        features=assessment.features,
        triggered_rules=assessment.triggered_rules,
        recommendation_for_io=assessment.recommendation_for_io
    )


@router.post("/monitor")
async def toggle_wallet_monitoring(
    request: WalletMonitorRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Register or unregister an address for background monitoring and instant SMS/Email alerts.
    """
    clean_addr = request.address.strip()
    target_chain = request.chain or detect_chain(clean_addr) or ChainType.TRON

    monitored_list = await redis_client.get_json("monitored_wallets") or []
    # Remove existing if present
    monitored_list = [m for m in monitored_list if m.get("address", "").lower() != clean_addr.lower()]

    if request.enable:
        monitored_list.append({
            "address": clean_addr,
            "chain": target_chain.value,
            "case_id": request.case_id,
            "registered_by": current_user.get("name", "LEA Officer")
        })

    await redis_client.set_json("monitored_wallets", monitored_list, expire_seconds=86400 * 30)

    return {
        "status": "SUCCESS",
        "address": clean_addr,
        "is_monitored": request.enable,
        "message": f"Address {clean_addr} {'now monitored' if request.enable else 'unmonitored'}."
    }
