"""
Application configuration using Pydantic v2 BaseSettings.
All sensitive parameters are dynamically loaded from environment variables.
"""

from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Global configuration settings for ChainSleuth backend."""

    # Application
    APP_NAME: str = "ChainSleuth"
    APP_ENV: str = "development"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    SECRET_KEY: str = "dev-secret-key-chainsleuth-sih2026-crypto-tracing"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    API_KEY_SECRET: str = "chainsleuth-lea-internal-api-secret-key"

    # PostgreSQL Relational Database
    POSTGRES_USER: str = "chainsleuth"
    POSTGRES_PASSWORD: str = "chainsleuth_secure_pass_2026"
    POSTGRES_DB: str = "chainsleuth_db"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    DATABASE_URL: str = "postgresql+asyncpg://chainsleuth:chainsleuth_secure_pass_2026@localhost:5432/chainsleuth_db"

    # Redis Cache & PubSub
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_URL: str = "redis://localhost:6379/0"

    # Neo4j Graph Database
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "chainsleuth_neo4j_pass_2026"

    # Celery Task Queue
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # Blockchain APIs
    # Tron (TronGrid) - Primary Chain for Indian Cyber Fraud (USDT-TRC20)
    TRONGRID_API_KEY: str = ""
    TRON_GRID_URL: str = "https://api.trongrid.io"
    TRON_FULL_NODE_URL: str = "https://api.trongrid.io"

    # Ethereum (Etherscan API)
    ETHERSCAN_API_KEY: str = ""
    ETHERSCAN_API_URL: str = "https://api.etherscan.io/api"
    ETH_RPC_URL: str = "https://cloudflare-eth.com"

    # Solana (Helius API)
    HELIUS_API_KEY: str = ""
    HELIUS_RPC_URL: str = "https://mainnet.helius-rpc.com"

    # Tracing Engine Parameters
    MAX_TRACE_HOPS: int = 5
    MAX_BRANCHING_FACTOR: int = 10
    DEFAULT_MIN_AMOUNT_USD: float = 10.0
    DUST_THRESHOLD_USD: float = 2.0
    TRACE_TIMEOUT_SECONDS: int = 180

    # Law Enforcement Requisitions & Alerts
    LEA_ORGANIZATION: str = "State Cyber Crime Police / SIH26183"
    ALERT_WEBHOOK_URL: str = "http://localhost:8000/api/v1/alerts/test-webhook"
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = "cybercell-alerts@chainsleuth.gov.in"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


@lru_cache()
def get_settings() -> Settings:
    """Return a cached instance of application settings."""
    return Settings()
