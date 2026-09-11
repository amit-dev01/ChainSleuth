"""
Exchange and VASP attribution service.
Identifies whether wallet addresses belong to centralized exchanges (Binance, WazirX, CoinDCX),
decentralized protocols, or mixers, and returns legal nodal contact details for asset freeze.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List

from backend.config.chains import ChainType
from backend.storage.redis_client import redis_client

logger = logging.getLogger(__name__)

SEED_DIR = Path(__file__).parent / "seed_data"


class ExchangeService:
    """Service for address attribution and VASP entity lookup."""

    def __init__(self) -> None:
        # Key: (chain.lower(), address.lower()) -> Entity dict
        self._registry: Dict[str, Dict[str, Any]] = {}
        self._load_seed_data()

    def _load_seed_data(self) -> None:
        """Load curated seed databases for Tron, Ethereum, and Solana."""
        seed_files = {
            ChainType.TRON.value: SEED_DIR / "tron_exchanges.json",
            ChainType.ETHEREUM.value: SEED_DIR / "eth_exchanges.json",
            ChainType.SOLANA.value: SEED_DIR / "solana_exchanges.json",
        }

        total_loaded = 0
        for chain, file_path in seed_files.items():
            if file_path.exists():
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        for item in data:
                            addr = item["address"].strip().lower()
                            key = f"{chain}:{addr}"
                            self._registry[key] = item
                            total_loaded += 1
                except Exception as exc:
                    logger.error("Failed loading exchange seed file %s: %s", file_path, exc)

        logger.info("Loaded %d known exchange and entity records into memory.", total_loaded)

    async def identify_address(self, address: str, chain: str) -> Optional[Dict[str, Any]]:
        """
        Identify if an address belongs to a known exchange, mixer, or service.

        :param address: Target blockchain address.
        :param chain: Blockchain network identifier.
        :return: Entity metadata dictionary or None.
        """
        cleaned_chain = chain.lower()
        cleaned_addr = address.strip().lower()
        key = f"{cleaned_chain}:{cleaned_addr}"

        # 1. Check in-memory registry (Fastest)
        if key in self._registry:
            return self._registry[key]

        # 2. Check Redis cache
        cached = await redis_client.get_json(f"entity:{key}")
        if cached:
            return cached

        return None

    def is_terminal_vasp(self, entity: Optional[Dict[str, Any]]) -> bool:
        """
        Check if the entity represents a terminal node (e.g. CEX deposit or hot wallet)
        where law enforcement can freeze assets.
        """
        if not entity:
            return False
        return entity.get("entity_type") in ("CEX", "INSTANT_EXCHANGE", "MIXER")

    async def register_attribution(
        self,
        address: str,
        chain: str,
        name: str,
        entity_type: str = "CEX",
        role: str = "HOT_WALLET",
        nodal_email: Optional[str] = None,
        fiu_registered: bool = False
    ) -> Dict[str, Any]:
        """Dynamically add or override an address attribution."""
        cleaned_chain = chain.lower()
        cleaned_addr = address.strip().lower()
        key = f"{cleaned_chain}:{cleaned_addr}"

        entity_data = {
            "address": address.strip(),
            "name": name,
            "entity_type": entity_type,
            "chain": cleaned_chain,
            "role": role,
            "nodal_email": nodal_email or "compliance@vasp.internal",
            "fiu_registered": fiu_registered,
            "risk_rating": "LOW" if fiu_registered else "MEDIUM"
        }

        self._registry[key] = entity_data
        await redis_client.set_json(f"entity:{key}", entity_data, expire_seconds=86400 * 7)
        return entity_data

    def get_all_known_entities(self) -> List[Dict[str, Any]]:
        """Return all in-memory registered entities."""
        return list(self._registry.values())


# Global service singleton
exchange_service = ExchangeService()


def get_exchange_service() -> ExchangeService:
    """Dependency provider for FastAPI and Tracer."""
    return exchange_service
