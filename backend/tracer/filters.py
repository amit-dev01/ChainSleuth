"""
Pruning heuristics and transaction filter rules for BFS graph traversal.
Eliminates spam, zero-value address poisoning attacks, and dust transactions.
"""

from typing import List, Set
from backend.adapters.models import Transfer


class TraceFilter:
    """Filter algorithms to prevent graph explosion and isolate relevant fraud flows."""

    def __init__(
        self,
        min_amount_usd: float = 10.0,
        max_branches_per_node: int = 8,
        min_timestamp: int = 0
    ) -> None:
        self.min_amount_usd = min_amount_usd
        self.max_branches_per_node = max_branches_per_node
        self.min_timestamp = min_timestamp

    def filter_transfers(
        self,
        transfers: List[Transfer],
        current_wallet: str,
        visited_addresses: Set[str]
    ) -> List[Transfer]:
        """
        Filter outgoing transfers from current wallet applying dust, time, and branching rules.
        """
        outgoing: List[Transfer] = []

        for tx in transfers:
            # Only consider outflows from the active node
            if tx.from_address.lower() != current_wallet.lower():
                continue

            # Eliminate zero-value address poisoning phishing attacks
            if tx.amount <= 0.0001:
                continue

            # Eliminate dust transactions below threshold
            if tx.amount < self.min_amount_usd:
                continue

            # Time filter (ignore historical txs prior to incident)
            if self.min_timestamp > 0 and tx.timestamp < self.min_timestamp:
                continue

            # Prevent circular loops
            if tx.to_address.lower() in visited_addresses:
                continue

            outgoing.append(tx)

        # Sort descending by transaction amount to prioritize highest value flows
        outgoing.sort(key=lambda t: t.amount, reverse=True)

        # Apply maximum branching factor
        return outgoing[:self.max_branches_per_node]
