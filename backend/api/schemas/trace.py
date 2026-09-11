"""
Pydantic v2 schemas for trace initiation, status querying, and graph visualization.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from backend.config.chains import ChainType
from backend.tracer.result import TraceResult


class StartTraceRequest(BaseModel):
    """Request payload to initiate a blockchain fund flow trace."""
    seed_address: str = Field(..., description="Suspect cryptocurrency wallet address reported by victim")
    chain: Optional[ChainType] = Field(None, description="Blockchain network (auto-detected if omitted)")
    max_hops: int = Field(5, ge=1, le=10, description="Maximum BFS graph traversal depth")
    min_amount_usd: float = Field(10.0, ge=0.0, description="Minimum transfer amount threshold in USD to prune dust")
    target_token: Optional[str] = Field("USDT", description="Target token to track (e.g. USDT, TRX, ETH)")
    case_id: Optional[str] = Field(None, description="Associated Law Enforcement Case / FIR number")
    async_mode: bool = Field(True, description="Execute asynchronously via Celery worker queue")

    model_config = ConfigDict(populate_by_name=True)


class TraceStatusResponse(BaseModel):
    """Response containing execution status, progress, and result payload."""
    job_id: str
    status: str = Field(..., description="PENDING, RUNNING, COMPLETED, FAILED")
    progress_pct: int = Field(0, ge=0, le=100)
    message: Optional[str] = None
    result: Optional[TraceResult] = None

    model_config = ConfigDict(populate_by_name=True)


class GraphVisualizationResponse(BaseModel):
    """Forensic graph structure formatted for frontend visualization (Cytoscape/Vis.js)."""
    seed_address: str
    chain: str
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]

    model_config = ConfigDict(populate_by_name=True)
