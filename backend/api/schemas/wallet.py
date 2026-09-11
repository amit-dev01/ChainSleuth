"""
Pydantic v2 schemas for wallet analysis, monitoring, and risk profiles.
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict
from backend.config.chains import ChainType


class WalletOverviewResponse(BaseModel):
    """Forensic overview of an address including holdings and entity classification."""
    address: str
    chain: str
    label: Optional[str] = None
    entity_name: Optional[str] = None
    entity_type: Optional[str] = "WALLET"
    native_balance: float = 0.0
    native_symbol: str = "TRX"
    token_balances: Dict[str, float] = Field(default_factory=dict)
    total_usd_value: float = 0.0
    risk_score: float = 0.0
    risk_tier: str = "LOW"
    is_monitored: bool = False

    model_config = ConfigDict(populate_by_name=True)


class WalletMonitorRequest(BaseModel):
    """Payload to register an address for live transaction monitoring."""
    address: str
    chain: Optional[ChainType] = None
    case_id: Optional[str] = "CASE-2026-CYBER"
    enable: bool = True

    model_config = ConfigDict(populate_by_name=True)


class WalletRiskResponse(BaseModel):
    """Detailed AML risk analysis response for cyber crime charge sheets."""
    address: str
    chain: str
    risk_score: float
    risk_tier: str
    is_suspicious: bool
    features: Dict[str, float]
    triggered_rules: List[Dict[str, Any]]
    recommendation_for_io: str

    model_config = ConfigDict(populate_by_name=True)
