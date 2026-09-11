"""
Pydantic v2 data models for tracing outputs, graph elements,
and multi-hop attribution paths for law enforcement charge sheets.
"""

from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field, ConfigDict
from backend.config.chains import ChainType


class TraceNode(BaseModel):
    """A node in the forensic transaction graph."""
    address: str
    chain: ChainType
    label: str = "Intermediate Wallet"
    entity_name: Optional[str] = None
    entity_type: Optional[str] = "WALLET"
    risk_score: float = 0.0
    hop_level: int = 0
    is_seed: bool = False
    is_terminal: bool = False
    fiu_registered: Optional[bool] = None
    nodal_email: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True)


class TraceEdge(BaseModel):
    """A directed fund transfer between two wallets."""
    tx_hash: str
    from_address: str
    to_address: str
    amount: float
    token_symbol: str = "USDT"
    timestamp: int
    block_number: Optional[int] = None
    hop: int = 1

    model_config = ConfigDict(populate_by_name=True)


class TracePath(BaseModel):
    """An end-to-end evidence trail from victim deposit to terminal VASP."""
    path_id: str
    hops: int
    initial_amount: float
    attributed_amount: float
    terminal_vasp: str
    terminal_address: str
    terminal_role: str = "HOT_WALLET"
    fiu_registered: bool = False
    nodal_email: Optional[str] = None
    obfuscation_indicators: List[str] = Field(default_factory=list)
    address_sequence: List[str] = Field(default_factory=list)
    transfers: List[TraceEdge] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)


class TraceResult(BaseModel):
    """Comprehensive trace audit result ready for court presentation."""
    job_id: str
    seed_address: str
    chain: ChainType
    target_token: str = "USDT"
    total_stolen_amount: float = 0.0
    total_attributed_amount: float = 0.0
    attribution_percentage: float = 0.0
    destination_vasps: List[Dict[str, Any]] = Field(default_factory=list)
    paths: List[TracePath] = Field(default_factory=list)
    nodes: List[TraceNode] = Field(default_factory=list)
    edges: List[TraceEdge] = Field(default_factory=list)
    obfuscation_detected: List[Dict[str, Any]] = Field(default_factory=list)
    overall_risk_score: float = 0.0
    risk_tier: str = "LOW"
    duration_seconds: float = 0.0
    completed_at: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True)
