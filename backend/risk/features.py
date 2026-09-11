"""
Feature extraction pipeline for wallet behavior and transaction risk assessment.
Extracts behavioral signals used by rule engine and machine learning classifiers.
"""

from typing import List, Dict, Any
from backend.adapters.models import Transfer, WalletBalance


class FeatureExtractor:
    """Extracts analytical features from a wallet's transaction history."""

    @staticmethod
    def extract_features(
        address: str,
        transfers: List[Transfer],
        balance: WalletBalance
    ) -> Dict[str, float]:
        """
        Extract numerical features characterizing wallet behavioral patterns.
        """
        if not transfers:
            return {
                "total_volume": 0.0,
                "tx_count": 0.0,
                "avg_tx_size": 0.0,
                "inflow_outflow_ratio": 0.0,
                "velocity_tx_per_hour": 0.0,
                "holding_duration_hours": 0.0,
                "unique_counterparties": 0.0,
                "current_balance": balance.token_balances.get("USDT", 0.0),
                "is_zero_balance_mule": 1.0 if balance.token_balances.get("USDT", 0.0) < 1.0 else 0.0
            }

        inflows = [t for t in transfers if t.to_address.lower() == address.lower()]
        outflows = [t for t in transfers if t.from_address.lower() == address.lower()]

        total_in_amt = sum(t.amount for t in inflows)
        total_out_amt = sum(t.amount for t in outflows)
        total_volume = total_in_amt + total_out_amt

        # Lifespan
        timestamps = [t.timestamp for t in transfers]
        first_seen = min(timestamps)
        last_seen = max(timestamps)
        duration_seconds = max(last_seen - first_seen, 60)
        duration_hours = duration_seconds / 3600.0

        # Counterparties
        counterparties = set()
        for t in inflows:
            counterparties.add(t.from_address.lower())
        for t in outflows:
            counterparties.add(t.to_address.lower())

        velocity = len(transfers) / max(duration_hours, 1.0)
        in_out_ratio = total_out_amt / (total_in_amt if total_in_amt > 0 else 1.0)

        usdt_bal = balance.token_balances.get("USDT", 0.0)
        # Mule wallets usually keep near-zero balance after pass-through
        is_mule = 1.0 if (total_volume > 1000 and usdt_bal < 10.0 and in_out_ratio >= 0.90) else 0.0

        return {
            "total_volume": round(total_volume, 2),
            "tx_count": float(len(transfers)),
            "avg_tx_size": round(total_volume / len(transfers), 2),
            "inflow_outflow_ratio": round(in_out_ratio, 3),
            "velocity_tx_per_hour": round(velocity, 2),
            "holding_duration_hours": round(duration_hours, 2),
            "unique_counterparties": float(len(counterparties)),
            "current_balance": round(usdt_bal, 2),
            "is_zero_balance_mule": is_mule
        }
