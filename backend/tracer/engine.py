"""
Core Breadth-First Search (BFS) Blockchain Tracing Engine.
Traverses transaction hops in real time, tags destination exchanges (VASPs),
stores graph topologies in Neo4j, and generates court-ready forensic attribution trails.
"""

import asyncio
from collections import deque
import logging
import time
import uuid
from typing import Dict, Any, List, Optional, Set, Callable, Awaitable

from backend.adapters.base import BaseAdapter
from backend.adapters.models import Transfer
from backend.adapters.tron_adapter import TronAdapter
from backend.adapters.eth_adapter import EthereumAdapter
from backend.adapters.solana_adapter import SolanaAdapter
from backend.config.chains import ChainType, detect_chain
from backend.config.settings import get_settings
from backend.exchange_db.service import exchange_service
from backend.storage.neo4j_client import neo4j_client
from backend.tracer.filters import TraceFilter
from backend.tracer.obfuscation import ObfuscationDetector
from backend.tracer.result import TraceResult, TracePath, TraceNode, TraceEdge

logger = logging.getLogger(__name__)
settings = get_settings()


class BFSTracerEngine:
    """High-speed asynchronous BFS tracing engine."""

    def __init__(self) -> None:
        self.adapters: Dict[ChainType, BaseAdapter] = {
            ChainType.TRON: TronAdapter(),
            ChainType.ETHEREUM: EthereumAdapter(),
            ChainType.SOLANA: SolanaAdapter(),
        }

    def get_adapter(self, chain: ChainType) -> BaseAdapter:
        """Retrieve network adapter for given chain."""
        adapter = self.adapters.get(chain)
        if not adapter:
            raise ValueError(f"Unsupported blockchain network: {chain}")
        return adapter

    async def run_trace(
        self,
        seed_address: str,
        chain: Optional[ChainType] = None,
        max_hops: int = 5,
        min_amount_usd: float = 10.0,
        start_timestamp: Optional[int] = None,
        progress_callback: Optional[Callable[[int, str], Awaitable[None]]] = None
    ) -> TraceResult:
        """
        Execute BFS multi-hop fund flow tracing from a suspect wallet address.
        """
        start_time = time.time()
        job_id = str(uuid.uuid4())

        # Determine chain automatically if not specified
        target_chain = chain or detect_chain(seed_address) or ChainType.TRON
        adapter = self.get_adapter(target_chain)

        logger.info(
            "Starting BFS trace for %s on %s (max_hops=%d, min_amount=$%.2f)",
            seed_address, target_chain.value, max_hops, min_amount_usd
        )

        trace_filter = TraceFilter(
            min_amount_usd=min_amount_usd,
            max_branches_per_node=settings.MAX_BRANCHING_FACTOR,
            min_timestamp=start_timestamp or 0
        )

        visited_addresses: Set[str] = set()
        nodes_dict: Dict[str, TraceNode] = {}
        edges_list: List[TraceEdge] = []
        terminal_paths: List[TracePath] = []
        obfuscation_events: List[Dict[str, Any]] = []

        total_stolen_amount = 0.0
        total_attributed_amount = 0.0

        # Queue elements: (address, hop_level, [path_transfers], current_amount)
        queue = deque([(seed_address, 0, [], 0.0)])
        visited_addresses.add(seed_address.lower())

        # Identify seed wallet
        seed_entity = await exchange_service.identify_address(seed_address, target_chain.value)
        seed_node = TraceNode(
            address=seed_address,
            chain=target_chain,
            label="Suspect / Seed Wallet",
            entity_name=seed_entity.get("name") if seed_entity else "Suspect Wallet",
            entity_type=seed_entity.get("entity_type") if seed_entity else "SUSPECT_WALLET",
            risk_score=95.0,
            hop_level=0,
            is_seed=True,
            is_terminal=False
        )
        nodes_dict[seed_address] = seed_node

        await neo4j_client.upsert_wallet(
            address=seed_address,
            chain=target_chain.value,
            label=seed_node.label,
            entity_name=seed_node.entity_name,
            entity_type=seed_node.entity_type,
            risk_score=seed_node.risk_score,
            is_seed=True
        )

        total_steps = 0
        max_allowed_steps = 50

        while queue and total_steps < max_allowed_steps:
            current_addr, current_hop, path_so_far, current_amt = queue.popleft()
            total_steps += 1

            if progress_callback:
                pct = min(95, int((total_steps / max_allowed_steps) * 100))
                await progress_callback(pct, f"Inspecting hop {current_hop}: {current_addr[:10]}...")

            # Check if this node is a known Exchange, Mixer, or VASP
            entity = await exchange_service.identify_address(current_addr, target_chain.value)

            if current_hop > 0 and exchange_service.is_terminal_vasp(entity):
                # We reached a terminal exchange or mixer
                vasp_name = entity["name"]
                logger.info("Destination VASP reached at hop %d: %s (%s)", current_hop, vasp_name, current_addr)

                total_attributed_amount += current_amt

                # Mark node as terminal
                if current_addr in nodes_dict:
                    nodes_dict[current_addr].is_terminal = True
                    nodes_dict[current_addr].entity_name = vasp_name
                    nodes_dict[current_addr].entity_type = entity.get("entity_type", "CEX")
                    nodes_dict[current_addr].label = f"{vasp_name} ({entity.get('role', 'HOT_WALLET')})"
                    nodes_dict[current_addr].fiu_registered = entity.get("fiu_registered", False)
                    nodes_dict[current_addr].nodal_email = entity.get("nodal_email")

                # Record successful attribution path
                path_edge_models = [
                    TraceEdge(
                        tx_hash=tx.tx_hash,
                        from_address=tx.from_address,
                        to_address=tx.to_address,
                        amount=tx.amount,
                        token_symbol=tx.token_symbol,
                        timestamp=tx.timestamp,
                        block_number=tx.block_number,
                        hop=idx + 1
                    )
                    for idx, tx in enumerate(path_so_far)
                ]

                # Check for obfuscation indicators on this path
                path_indicators = []
                rapid_hops = ObfuscationDetector.detect_rapid_hopping(path_so_far)
                if rapid_hops:
                    path_indicators.append("RAPID_HOPPING")
                    obfuscation_events.extend(rapid_hops)

                if ObfuscationDetector.detect_mixer(entity.get("entity_type")):
                    path_indicators.append("MIXER_INTERACTION")
                elif ObfuscationDetector.detect_instant_exchange(entity.get("entity_type")):
                    path_indicators.append("NO_KYC_SWAP")

                path_obj = TracePath(
                    path_id=f"path_{len(terminal_paths) + 1}",
                    hops=current_hop,
                    initial_amount=path_so_far[0].amount if path_so_far else current_amt,
                    attributed_amount=current_amt,
                    terminal_vasp=vasp_name,
                    terminal_address=current_addr,
                    terminal_role=entity.get("role", "HOT_WALLET"),
                    fiu_registered=entity.get("fiu_registered", False),
                    nodal_email=entity.get("nodal_email"),
                    obfuscation_indicators=path_indicators,
                    address_sequence=[tx.from_address for tx in path_so_far] + [current_addr],
                    transfers=path_edge_models
                )
                terminal_paths.append(path_obj)

                # Stop traversing deeper into exchange internal hot wallets
                continue

            # If reached maximum hop depth, terminate this branch
            if current_hop >= max_hops:
                continue

            # Fetch outgoing transfers for current wallet
            try:
                transfers = await adapter.get_transfers(
                    address=current_addr,
                    limit=50,
                    start_timestamp=start_timestamp
                )
            except Exception as exc:
                logger.error("Error retrieving transfers for %s: %s", current_addr, exc)
                continue

            # Analyze peeling chain behavior
            peeling_result = ObfuscationDetector.detect_peeling_chain(transfers)
            if peeling_result:
                obfuscation_events.append({**peeling_result, "address": current_addr, "hop": current_hop})

            # Filter relevant transfers
            valid_outflows = trace_filter.filter_transfers(transfers, current_addr, visited_addresses)

            # Record initial amount at hop 0
            if current_hop == 0:
                total_stolen_amount = sum(tx.amount for tx in valid_outflows) or 1000.0

            for tx in valid_outflows:
                next_addr = tx.to_address
                visited_addresses.add(next_addr.lower())

                # Entity check for next node
                next_entity = await exchange_service.identify_address(next_addr, target_chain.value)

                # Store Node
                node = TraceNode(
                    address=next_addr,
                    chain=target_chain,
                    label=next_entity.get("name", "Intermediate Mule") if next_entity else "Mule Wallet",
                    entity_name=next_entity.get("name") if next_entity else None,
                    entity_type=next_entity.get("entity_type", "WALLET") if next_entity else "WALLET",
                    risk_score=85.0 if not next_entity else 20.0,
                    hop_level=current_hop + 1,
                    is_terminal=exchange_service.is_terminal_vasp(next_entity),
                    fiu_registered=next_entity.get("fiu_registered") if next_entity else None,
                    nodal_email=next_entity.get("nodal_email") if next_entity else None
                )
                nodes_dict[next_addr] = node

                # Store Edge
                edge = TraceEdge(
                    tx_hash=tx.tx_hash,
                    from_address=current_addr,
                    to_address=next_addr,
                    amount=tx.amount,
                    token_symbol=tx.token_symbol,
                    timestamp=tx.timestamp,
                    block_number=tx.block_number,
                    hop=current_hop + 1
                )
                edges_list.append(edge)

                # Save into Neo4j
                await neo4j_client.upsert_wallet(
                    address=next_addr,
                    chain=target_chain.value,
                    label=node.label,
                    entity_name=node.entity_name,
                    entity_type=node.entity_type,
                    risk_score=node.risk_score,
                    is_terminal=node.is_terminal
                )
                await neo4j_client.add_transfer_edge(
                    tx_hash=tx.tx_hash,
                    from_address=current_addr,
                    to_address=next_addr,
                    amount=tx.amount,
                    token_symbol=tx.token_symbol,
                    timestamp=tx.timestamp,
                    block_number=tx.block_number,
                    chain=target_chain.value
                )

                # Queue next hop
                queue.append((next_addr, current_hop + 1, path_so_far + [tx], tx.amount))

        duration = round(time.time() - start_time, 2)
        attribution_pct = (
            round((total_attributed_amount / total_stolen_amount) * 100, 2)
            if total_stolen_amount > 0
            else 0.0
        )

        # Unique destination VASPs
        vasp_summary: Dict[str, Dict[str, Any]] = {}
        for p in terminal_paths:
            v_name = p.terminal_vasp
            if v_name not in vasp_summary:
                vasp_summary[v_name] = {
                    "vasp_name": v_name,
                    "terminal_address": p.terminal_address,
                    "total_amount": 0.0,
                    "fiu_registered": p.fiu_registered,
                    "nodal_email": p.nodal_email,
                    "paths_count": 0
                }
            vasp_summary[v_name]["total_amount"] += p.attributed_amount
            vasp_summary[v_name]["paths_count"] += 1

        if progress_callback:
            await progress_callback(100, "Trace completed successfully.")

        return TraceResult(
            job_id=job_id,
            seed_address=seed_address,
            chain=target_chain,
            target_token="USDT",
            total_stolen_amount=round(total_stolen_amount, 2),
            total_attributed_amount=round(total_attributed_amount, 2),
            attribution_percentage=min(100.0, attribution_pct),
            destination_vasps=list(vasp_summary.values()),
            paths=terminal_paths,
            nodes=list(nodes_dict.values()),
            edges=edges_list,
            obfuscation_detected=obfuscation_events,
            overall_risk_score=92.0 if terminal_paths else 75.0,
            risk_tier="CRITICAL" if total_stolen_amount > 50000 else "HIGH",
            duration_seconds=duration,
            completed_at=time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
        )


# Global tracer engine singleton
tracer_engine = BFSTracerEngine()


def get_tracer_engine() -> BFSTracerEngine:
    """Dependency provider for FastAPI and background tasks."""
    return tracer_engine
