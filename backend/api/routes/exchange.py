"""
Exchange and VASP intelligence endpoints.
Allows LEA officers to query known exchange hot wallets, view FIU-India status, and submit custom tags.
"""

from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from backend.api.middleware.auth import get_current_user
from backend.config.chains import detect_chain, ChainType
from backend.exchange_db.service import exchange_service

router = APIRouter(prefix="/exchange", tags=["VASP Directory & Tagging"])


class CustomTagRequest(BaseModel):
    """Payload to tag an address with custom intelligence."""
    address: str = Field(..., description="Target wallet address")
    chain: Optional[ChainType] = Field(None, description="Blockchain network")
    name: str = Field(..., description="Entity or Exchange Name (e.g. Binance, WazirX, Scam Mule Group)")
    entity_type: str = Field("CEX", description="CEX, DEX, MIXER, MULE_NETWORK, BRIDGE")
    role: str = Field("HOT_WALLET", description="HOT_WALLET, DEPOSIT_SWEEPER, TREASURY")
    nodal_email: Optional[str] = Field(None, description="Compliance nodal contact email")
    fiu_registered: bool = Field(False, description="Registered with FIU-India")


@router.get("/lookup/{address}")
async def lookup_address_attribution(
    address: str,
    chain: Optional[str] = Query(None, description="Blockchain network"),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Check if an address matches a known Centralized Exchange (VASP), Mixer, or DEX.
    """
    clean_addr = address.strip()
    target_chain = ChainType(chain.lower()) if chain else detect_chain(clean_addr) or ChainType.TRON

    entity = await exchange_service.identify_address(clean_addr, target_chain.value)
    if not entity:
        return {
            "address": clean_addr,
            "chain": target_chain.value,
            "is_attributed": False,
            "entity": None,
            "message": "Address is unclassified or belongs to an unmapped private individual."
        }

    return {
        "address": clean_addr,
        "chain": target_chain.value,
        "is_attributed": True,
        "entity": entity,
        "is_terminal_vasp": exchange_service.is_terminal_vasp(entity)
    }


@router.get("/list")
async def list_known_exchanges(
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """
    Retrieve list of all pre-seeded and verified exchanges, nodal contacts, and legal freezing portals.
    """
    return exchange_service.get_all_known_entities()


@router.post("/tag")
async def tag_custom_address(
    request: CustomTagRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Submit a law enforcement custom attribution tag for an address.
    """
    clean_addr = request.address.strip()
    target_chain = request.chain or detect_chain(clean_addr) or ChainType.TRON

    entity = await exchange_service.register_attribution(
        address=clean_addr,
        chain=target_chain.value,
        name=request.name,
        entity_type=request.entity_type,
        role=request.role,
        nodal_email=request.nodal_email,
        fiu_registered=request.fiu_registered
    )

    return {
        "status": "SUCCESS",
        "message": f"Address {clean_addr} successfully attributed to {request.name}.",
        "entity": entity
    }
