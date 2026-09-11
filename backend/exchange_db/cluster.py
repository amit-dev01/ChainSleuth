"""
Heuristic clustering algorithms for attributing cyber fraud mule networks.
Implements common deposit address clustering, sweep detection, and co-spending patterns.
"""

from typing import List, Dict, Set, Any
from backend.adapters.models import Transfer


class WalletClusterEngine:
    """Heuristic clustering algorithms for suspect wallet attribution."""

    @staticmethod
    def identify_deposit_sweeps(transfers: List[Transfer], sweep_threshold_pct: float = 0.90) -> List[Dict[str, Any]]:
        """
        Identify sweep behavior where incoming funds are almost immediately (or fully)
        forwarded in a single consolidated transaction to a primary hub.
        """
        sweeps: List[Dict[str, Any]] = []
        if len(transfers) < 2:
            return sweeps

        # Sort transfers chronologically
        sorted_txs = sorted(transfers, key=lambda t: t.timestamp)

        for i in range(len(sorted_txs) - 1):
            tx_in = sorted_txs[i]
            tx_out = sorted_txs[i + 1]

            # Inflow followed by outflow within 2 hours
            time_delta = tx_out.timestamp - tx_in.timestamp
            if 0 < time_delta <= 7200:
                ratio = tx_out.amount / (tx_in.amount if tx_in.amount > 0 else 1.0)
                if sweep_threshold_pct <= ratio <= 1.05:  # Accounting for small network fee deduction
                    sweeps.append({
                        "type": "RAPID_SWEEP",
                        "in_tx": tx_in.tx_hash,
                        "out_tx": tx_out.tx_hash,
                        "swept_amount": tx_out.amount,
                        "intermediate_wallet": tx_in.to_address,
                        "destination_wallet": tx_out.to_address,
                        "latency_seconds": time_delta
                    })

        return sweeps

    @staticmethod
    def cluster_by_common_destination(
        transfers_by_wallet: Dict[str, List[Transfer]]
    ) -> Dict[str, Set[str]]:
        """
        Identify wallets that deposit to the exact same destination address (e.g. shared mule or deposit vault).
        Returns: {destination_address: {wallet_A, wallet_B, ...}}
        """
        clusters: Dict[str, Set[str]] = {}

        for wallet, tx_list in transfers_by_wallet.items():
            for tx in tx_list:
                if tx.from_address.lower() == wallet.lower():
                    dest = tx.to_address.lower()
                    if dest not in clusters:
                        clusters[dest] = set()
                    clusters[dest].add(wallet)

        # Filter to destinations with 2 or more distinct senders (co-depositors)
        return {dest: senders for dest, senders in clusters.items() if len(senders) >= 2}

    @staticmethod
    def detect_fan_out_pattern(transfers: List[Transfer], min_recipients: int = 4) -> bool:
        """
        Detect sudden dispersal where one wallet splits funds into multiple recipient wallets
        in a brief burst (typical layer-2 obfuscation).
        """
        outgoing = [t for t in transfers if t.amount > 0]
        if len(outgoing) < min_recipients:
            return False

        unique_recipients = {t.to_address for t in outgoing}
        return len(unique_recipients) >= min_recipients
