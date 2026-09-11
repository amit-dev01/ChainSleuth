"""
Composite risk scoring engine combining deterministic AML rules and statistical models.
Generates an actionable risk tier (LOW, MEDIUM, HIGH, CRITICAL) and legal recommendations for IOs.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, ConfigDict

from backend.adapters.models import Transfer, WalletBalance
from backend.risk.features import FeatureExtractor
from backend.risk.rules import RiskRuleEngine


class RiskAssessment(BaseModel):
    """Forensic risk assessment output for a suspect wallet or trace operation."""
    address: str
    chain: str
    risk_score: float = Field(..., description="Risk score from 0.0 (clean) to 100.0 (extreme fraud risk)")
    risk_tier: str = Field(..., description="Risk tier: LOW, MEDIUM, HIGH, CRITICAL")
    is_suspicious: bool = True
    features: Dict[str, float] = Field(default_factory=dict)
    triggered_rules: List[Dict[str, Any]] = Field(default_factory=list)
    recommendation_for_io: str = Field(..., description="Legal recommendation for Investigating Officer")

    model_config = ConfigDict(populate_by_name=True)


class RiskScorer:
    """Calculates composite risk score and legal freezing recommendations."""

    @staticmethod
    def calculate_risk(
        address: str,
        chain: str,
        transfers: List[Transfer],
        balance: WalletBalance,
        obfuscation_events: Optional[List[Dict[str, Any]]] = None,
        vasp_attributions: Optional[List[Dict[str, Any]]] = None
    ) -> RiskAssessment:
        """
        Compute comprehensive risk score combining behavioral features and legal heuristics.
        """
        features = FeatureExtractor.extract_features(address, transfers, balance)
        rules = RiskRuleEngine.evaluate_rules(
            features=features,
            obfuscation_events=obfuscation_events or [],
            vasp_attributions=vasp_attributions or []
        )

        # Base score from triggered rule impacts
        base_score = sum(r.get("score_impact", 0.0) for r in rules)

        # Baseline risk for active tracing (suspect wallet starts at minimum 30 if volume exists)
        if features.get("total_volume", 0) > 500:
            base_score = max(base_score, 45.0)

        # Cap score between 0.0 and 100.0
        final_score = min(100.0, max(0.0, base_score))

        # Risk Tier Classification
        if final_score >= 80.0:
            tier = "CRITICAL"
        elif final_score >= 55.0:
            tier = "HIGH"
        elif final_score >= 25.0:
            tier = "MEDIUM"
        else:
            tier = "LOW"

        # Actionable recommendation for Cyber Cell IO
        if tier in ("CRITICAL", "HIGH"):
            recommendation = (
                "IMMEDIATE ACTION REQUIRED: Issue Section 91 CrPC / Section 94 BNSS requisition notice "
                "to destination VASP compliance nodal officers to freeze recipient deposit accounts "
                "and obtain KYC, IP login logs, and associated bank accounts."
            )
        elif tier == "MEDIUM":
            recommendation = (
                "MONITORING RECOMMENDED: Monitor wallet for subsequent outgoing hops. "
                "Verify victim transaction hash and initiate preliminary inquiry."
            )
        else:
            recommendation = "Low fraud indicators. Wallet activity appears normal or low volume."

        return RiskAssessment(
            address=address,
            chain=chain,
            risk_score=round(final_score, 1),
            risk_tier=tier,
            is_suspicious=(final_score >= 50.0),
            features=features,
            triggered_rules=rules,
            recommendation_for_io=recommendation
        )


# Global scorer singleton
risk_scorer = RiskScorer()


def get_risk_scorer() -> RiskScorer:
    """Dependency provider for risk scoring."""
    return risk_scorer
