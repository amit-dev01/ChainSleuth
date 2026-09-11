"""
Rule-based heuristic engine tailored for Indian cyber crime patterns (SIH26183).
Detects mule accounts, rapid pass-through laundering, and non-FIU offshore off-ramping.
"""

from typing import List, Dict, Any


class RiskRuleEngine:
    """Evaluates cyber fraud heuristic rules against extracted wallet features."""

    @staticmethod
    def evaluate_rules(
        features: Dict[str, float],
        obfuscation_events: List[Dict[str, Any]],
        vasp_attributions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Evaluate risk rules and return triggered risk factors with scores and legal descriptions.
        """
        triggered_rules: List[Dict[str, Any]] = []

        # 1. Zero-balance Mule Pass-through
        if features.get("is_zero_balance_mule", 0.0) == 1.0:
            triggered_rules.append({
                "rule_id": "RULE_MULE_PASS_THROUGH",
                "name": "Mule Account Pass-Through Pattern",
                "score_impact": 35.0,
                "severity": "HIGH",
                "description": (
                    f"Wallet transferred {features.get('total_volume', 0):.2f} USDT and currently holds "
                    f"under ${features.get('current_balance', 0):.2f}. Consistent with intermediary mule accounts."
                )
            })

        # 2. Rapid Turnover Velocity
        if features.get("velocity_tx_per_hour", 0.0) >= 3.0 and features.get("holding_duration_hours", 0.0) <= 24.0:
            triggered_rules.append({
                "rule_id": "RULE_HIGH_VELOCITY_CHURN",
                "name": "High-Velocity Automated Fund Movement",
                "score_impact": 20.0,
                "severity": "MEDIUM",
                "description": (
                    f"High transaction frequency ({features.get('velocity_tx_per_hour', 0):.1f} tx/hr) "
                    f"over short lifespan ({features.get('holding_duration_hours', 0):.1f} hrs)."
                )
            })

        # 3. Peeling Chain Obfuscation
        has_peeling = any(e.get("type") == "PEELING_CHAIN" for e in obfuscation_events)
        if has_peeling:
            triggered_rules.append({
                "rule_id": "RULE_PEELING_CHAIN",
                "name": "Peeling Chain Obfuscation Detected",
                "score_impact": 25.0,
                "severity": "HIGH",
                "description": "Systematic peeling of partial funds while routing remainder to fresh addresses."
            })

        # 4. Mixer / Tumbler Interaction
        has_mixer = any(
            v.get("entity_type") in ("MIXER", "TUMBLER") or "MIXER" in v.get("vasp_name", "")
            for v in vasp_attributions
        )
        if has_mixer:
            triggered_rules.append({
                "rule_id": "RULE_MIXER_EXPOSURE",
                "name": "Interaction with Anonymizing Mixer / Tumbler",
                "score_impact": 40.0,
                "severity": "CRITICAL",
                "description": "Direct interaction with privacy-enhancing mixer (e.g. Tornado Cash or Tron mixer)."
            })

        # 5. Non-FIU Registered Offshore VASP
        non_fiu = any(
            not v.get("fiu_registered", True) and v.get("vasp_name") not in ("Unknown", "Unattributed")
            for v in vasp_attributions
        )
        if non_fiu:
            triggered_rules.append({
                "rule_id": "RULE_OFFSHORE_NON_FIU",
                "name": "Off-Ramped to Non-FIU Registered Entity",
                "score_impact": 20.0,
                "severity": "HIGH",
                "description": "Funds routed to foreign VASP or instant swapper not registered with FIU-India."
            })

        return triggered_rules
