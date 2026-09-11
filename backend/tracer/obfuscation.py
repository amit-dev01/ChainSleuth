"""
Obfuscation and anti-money laundering (AML) pattern detectors.
Identifies peeling chains, mixer hops, automated rapid hopping, and fan-out/fan-in layering.
"""

from typing import List, Dict, Any, Optional
from backend.adapters.models import Transfer


class ObfuscationDetector:
    """Detects crypto laundering techniques employed by fraud syndicates."""

    @staticmethod
    def detect_mixer(entity_type: Optional[str]) -> bool:
        """Flag mixer and tumbling protocols."""
        return entity_type in ("MIXER", "TUMBLER")

    @staticmethod
    def detect_instant_exchange(entity_type: Optional[str]) -> bool:
        """Flag non-KYC instant swap services frequently used as off-ramps."""
        return entity_type == "INSTANT_EXCHANGE"

    @staticmethod
    def detect_rapid_hopping(hop_transfers: List[Transfer], max_latency_seconds: int = 600) -> List[Dict[str, Any]]:
        """
        Flag consecutive hops occurring within < 10 minutes (indicating automated bot scripts).
        """
        rapid_hops: List[Dict[str, Any]] = []
        for i in range(len(hop_transfers) - 1):
            t1 = hop_transfers[i]
            t2 = hop_transfers[i + 1]
            diff = t2.timestamp - t1.timestamp
            if 0 <= diff <= max_latency_seconds:
                rapid_hops.append({
                    "type": "RAPID_HOPPING",
                    "latency_seconds": diff,
                    "hop_from": t1.to_address,
                    "hop_to": t2.to_address,
                    "amount": t2.amount,
                    "indicator": f"Automated pass-through within {diff}s"
                })
        return rapid_hops

    @staticmethod
    def detect_peeling_chain(transfers: List[Transfer]) -> Optional[Dict[str, Any]]:
        """
        Detect peeling chain pattern: an address receives an amount, sends a small portion
        to an external entity, and sweeps the majority remainder to a fresh change address.
        """
        if len(transfers) < 2:
            return None

        # Look for 1 small output (10-30%) and 1 dominant output (70-90%)
        outflows = [t for t in transfers if t.amount > 0]
        if len(outflows) == 2:
            amt1, amt2 = outflows[0].amount, outflows[1].amount
            total = amt1 + amt2
            ratio1 = amt1 / total
            ratio2 = amt2 / total

            if (0.05 <= ratio1 <= 0.35 and 0.65 <= ratio2 <= 0.95) or (0.05 <= ratio2 <= 0.35 and 0.65 <= ratio1 <= 0.95):
                peeled = min(amt1, amt2)
                remainder = max(amt1, amt2)
                return {
                    "type": "PEELING_CHAIN",
                    "peeled_amount": peeled,
                    "remainder_amount": remainder,
                    "indicator": f"Peeled {peeled:.2f} USDT, forwarded {remainder:.2f} USDT to fresh change address"
                }
        return None
