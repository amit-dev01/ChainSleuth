"""
Neo4j Graph Database client for high-performance blockchain network traversal.
Stores wallet nodes, transaction edges, and executes shortest path queries to VASPs.
Includes in-memory graph fallback for testing and offline development.
"""

import logging
from typing import Dict, Any, List, Optional

try:
    from neo4j import AsyncGraphDatabase, AsyncDriver
except ImportError:
    AsyncGraphDatabase = None
    AsyncDriver = Any

from backend.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class Neo4jClient:
    """Async Neo4j Client with graph querying and local memory fallback."""

    def __init__(self) -> None:
        self.driver: Optional[Any] = None
        self._connected: bool = False
        # In-memory graph storage fallback
        self._memory_nodes: Dict[str, Dict[str, Any]] = {}
        self._memory_edges: List[Dict[str, Any]] = []

    async def connect(self) -> None:
        """Connect to Neo4j instance and create schema constraints."""
        if AsyncGraphDatabase is None:
            self._connected = False
            logger.info("neo4j driver not installed. Using in-memory graph engine fallback.")
            return

        try:
            self.driver = AsyncGraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
                connection_timeout=3.0
            )
            await self.driver.verify_connectivity()
            self._connected = True
            logger.info("Connected to Neo4j successfully at %s", settings.NEO4J_URI)
            await self.init_schema()
        except Exception as exc:
            self._connected = False
            logger.warning(
                "Could not connect to Neo4j at %s: %s. Using in-memory graph fallback.",
                settings.NEO4J_URI, exc
            )

    async def close(self) -> None:
        """Close Neo4j driver connection."""
        if self.driver and self._connected:
            await self.driver.close()
            self._connected = False

    async def init_schema(self) -> None:
        """Initialize uniqueness constraints and indices."""
        if not self._connected or not self.driver:
            return

        constraint_queries = [
            "CREATE CONSTRAINT wallet_address_unique IF NOT EXISTS FOR (w:Wallet) REQUIRE (w.address, w.chain) IS UNIQUE;",
            "CREATE INDEX wallet_address_index IF NOT EXISTS FOR (w:Wallet) ON (w.address);",
            "CREATE INDEX wallet_entity_index IF NOT EXISTS FOR (w:Wallet) ON (w.entity_name);",
        ]

        async with self.driver.session() as session:
            for query in constraint_queries:
                try:
                    await session.run(query)
                except Exception as exc:
                    logger.debug("Neo4j schema query notification: %s", exc)

    async def upsert_wallet(
        self,
        address: str,
        chain: str,
        label: Optional[str] = None,
        entity_name: Optional[str] = None,
        entity_type: Optional[str] = None,
        risk_score: float = 0.0,
        is_seed: bool = False,
        is_terminal: bool = False
    ) -> None:
        """Upsert a wallet node into Neo4j graph."""
        node_key = f"{chain}:{address}"
        node_data = {
            "address": address,
            "chain": chain,
            "label": label or "Unknown",
            "entity_name": entity_name or "Unattributed",
            "entity_type": entity_type or "WALLET",
            "risk_score": risk_score,
            "is_seed": is_seed,
            "is_terminal": is_terminal
        }

        # Always update memory fallback
        self._memory_nodes[node_key] = node_data

        if self._connected and self.driver:
            query = """
            MERGE (w:Wallet {address: $address, chain: $chain})
            ON CREATE SET
                w.label = $label,
                w.entity_name = $entity_name,
                w.entity_type = $entity_type,
                w.risk_score = $risk_score,
                w.is_seed = $is_seed,
                w.is_terminal = $is_terminal,
                w.created_at = datetime()
            ON MATCH SET
                w.entity_name = coalesce($entity_name, w.entity_name),
                w.entity_type = coalesce($entity_type, w.entity_type),
                w.risk_score = CASE WHEN $risk_score > 0 THEN $risk_score ELSE w.risk_score END,
                w.is_terminal = CASE WHEN $is_terminal THEN true ELSE w.is_terminal END
            """
            try:
                async with self.driver.session() as session:
                    await session.run(query, **node_data)
            except Exception as exc:
                logger.error("Error upserting wallet node in Neo4j: %s", exc)

    async def add_transfer_edge(
        self,
        tx_hash: str,
        from_address: str,
        to_address: str,
        amount: float,
        token_symbol: str,
        timestamp: int,
        block_number: Optional[int],
        chain: str
    ) -> None:
        """Add or update a directed transfer relationship between two wallets."""
        edge_data = {
            "tx_hash": tx_hash,
            "from_address": from_address,
            "to_address": to_address,
            "amount": amount,
            "token_symbol": token_symbol,
            "timestamp": timestamp,
            "block_number": block_number or 0,
            "chain": chain
        }

        # Update in-memory fallback
        if not any(e["tx_hash"] == tx_hash and e["from_address"] == from_address and e["to_address"] == to_address for e in self._memory_edges):
            self._memory_edges.append(edge_data)

        if self._connected and self.driver:
            query = """
            MATCH (from:Wallet {address: $from_address, chain: $chain})
            MATCH (to:Wallet {address: $to_address, chain: $chain})
            MERGE (from)-[r:TRANSFERRED {tx_hash: $tx_hash}]->(to)
            ON CREATE SET
                r.amount = $amount,
                r.token_symbol = $token_symbol,
                r.timestamp = $timestamp,
                r.block_number = $block_number,
                r.chain = $chain
            """
            try:
                async with self.driver.session() as session:
                    await session.run(query, **edge_data)
            except Exception as exc:
                logger.error("Error creating transfer edge in Neo4j: %s", exc)

    async def get_subgraph(self, seed_address: str, chain: str, max_depth: int = 5) -> Dict[str, Any]:
        """
        Extract the traced subgraph for frontend graph visualization (Cytoscape / VisJS / D3).
        """
        if self._connected and self.driver:
            query = """
            MATCH path = (seed:Wallet {address: $seed_address, chain: $chain})-[r:TRANSFERRED*1..5]->(target:Wallet)
            WITH collect(nodes(path)) AS all_nodes, collect(relationships(path)) AS all_edges
            UNWIND all_nodes AS n_list
            UNWIND n_list AS n
            WITH DISTINCT n, all_edges
            WITH collect(DISTINCT {
                id: n.address,
                label: n.label,
                entity_name: n.entity_name,
                entity_type: n.entity_type,
                risk_score: n.risk_score,
                is_seed: n.is_seed,
                is_terminal: n.is_terminal
            }) AS nodes, all_edges
            UNWIND all_edges AS e_list
            UNWIND e_list AS e
            RETURN nodes, collect(DISTINCT {
                id: e.tx_hash,
                source: startNode(e).address,
                target: endNode(e).address,
                amount: e.amount,
                token: e.token_symbol,
                timestamp: e.timestamp
            }) AS edges
            """
            try:
                async with self.driver.session() as session:
                    result = await session.run(query, seed_address=seed_address, chain=chain)
                    record = await result.single()
                    if record:
                        return {
                            "nodes": record["nodes"],
                            "edges": record["edges"]
                        }
            except Exception as exc:
                logger.error("Error retrieving subgraph from Neo4j: %s", exc)

        # In-memory fallback subgraph
        nodes_list = [
            {"id": n["address"], **n}
            for n in self._memory_nodes.values()
            if n["chain"] == chain
        ]
        edges_list = [
            {
                "id": e["tx_hash"],
                "source": e["from_address"],
                "target": e["to_address"],
                "amount": e["amount"],
                "token": e["token_symbol"],
                "timestamp": e["timestamp"]
            }
            for e in self._memory_edges
            if e["chain"] == chain
        ]
        return {"nodes": nodes_list, "edges": edges_list}

    async def clear_all(self) -> None:
        """Clear graph data (used in tests)."""
        self._memory_nodes.clear()
        self._memory_edges.clear()
        if self._connected and self.driver:
            async with self.driver.session() as session:
                await session.run("MATCH (n) DETACH DELETE n")


# Global neo4j client instance
neo4j_client = Neo4jClient()


async def get_neo4j() -> Neo4jClient:
    """FastAPI dependency for Neo4j client."""
    return neo4j_client
