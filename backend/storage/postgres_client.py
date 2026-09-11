"""
PostgreSQL storage client using SQLAlchemy 2.0 asyncpg.
Manages relational data for cases, suspect wallets, trace jobs, and alerts.
"""

import logging
from datetime import datetime
from typing import AsyncGenerator, Optional
import uuid

from sqlalchemy import (
    Column,
    String,
    Float,
    Integer,
    Boolean,
    DateTime,
    Text,
    JSON,
    ForeignKey,
    Index
)
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine
)
from sqlalchemy.orm import DeclarativeBase, relationship

from backend.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Asynchronous SQLAlchemy Engine with fallback for standalone test environments
try:
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20
    )
except Exception as exc:
    logger.info("Using in-memory SQLite async engine fallback: %s", exc)
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)


class Base(DeclarativeBase):
    """Base declarative class for all relational models."""
    pass


class Case(Base):
    """Law Enforcement Case / Crime Report model."""
    __tablename__ = "cases"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_number = Column(String(64), unique=True, nullable=False, index=True)
    fir_number = Column(String(64), nullable=True)
    police_station = Column(String(128), nullable=True)
    state = Column(String(64), default="India")
    io_name = Column(String(128), nullable=False)
    io_email = Column(String(128), nullable=False)
    io_phone = Column(String(32), nullable=True)
    victim_name = Column(String(128), nullable=True)
    victim_loss_inr = Column(Float, default=0.0)
    victim_loss_crypto = Column(Float, default=0.0)
    target_token = Column(String(16), default="USDT")
    status = Column(String(32), default="ACTIVE", index=True)  # ACTIVE, UNDER_INVESTIGATION, ASSETS_FROZEN, CLOSED
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    wallets = relationship("SuspectWallet", back_populates="case", cascade="all, delete-orphan")
    traces = relationship("TraceJob", back_populates="case", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="case", cascade="all, delete-orphan")


class SuspectWallet(Base):
    """Suspect wallet addresses associated with cyber fraud cases."""
    __tablename__ = "suspect_wallets"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id = Column(String(36), ForeignKey("cases.id", ondelete="CASCADE"), nullable=True, index=True)
    address = Column(String(128), nullable=False, index=True)
    chain = Column(String(32), nullable=False, index=True)  # tron, ethereum, solana
    label = Column(String(128), nullable=True)  # e.g. "Victim Payment Wallet", "Mule Wallet"
    risk_score = Column(Float, default=0.0)
    risk_tier = Column(String(32), default="UNKNOWN")  # LOW, MEDIUM, HIGH, CRITICAL
    is_monitored = Column(Boolean, default=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    case = relationship("Case", back_populates="wallets")


class TraceJob(Base):
    """Execution status and metadata for graph tracing operations."""
    __tablename__ = "trace_jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id = Column(String(36), ForeignKey("cases.id", ondelete="SET NULL"), nullable=True, index=True)
    seed_address = Column(String(128), nullable=False, index=True)
    chain = Column(String(32), nullable=False)
    target_token = Column(String(16), default="USDT")
    max_hops = Column(Integer, default=5)
    min_amount_usd = Column(Float, default=10.0)
    status = Column(String(32), default="PENDING", index=True)  # PENDING, RUNNING, COMPLETED, FAILED
    progress_pct = Column(Integer, default=0)
    destination_vasp = Column(String(128), nullable=True)  # e.g. "Binance", "WazirX", "CoinDCX"
    deposit_address = Column(String(128), nullable=True)
    total_stolen_amount = Column(Float, default=0.0)
    total_attributed_amount = Column(Float, default=0.0)
    nodes_discovered = Column(Integer, default=0)
    edges_discovered = Column(Integer, default=0)
    result_summary = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    case = relationship("Case", back_populates="traces")


class IdentifiedExchange(Base):
    """Database of known VASPs, exchanges, and nodal contact details."""
    __tablename__ = "identified_exchanges"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(128), nullable=False, unique=True, index=True)
    entity_type = Column(String(32), default="CEX")  # CEX, DEX, MIXER, BRIDGE, P2P_MERCHANT
    jurisdiction = Column(String(64), default="Global")  # India, Seychelles, Cayman Islands, etc.
    fiu_ind_registered = Column(Boolean, default=False)  # Registered with FIU-IND
    nodal_officer_email = Column(String(128), nullable=True)
    law_enforcement_portal = Column(String(256), nullable=True)
    response_sla_hours = Column(Integer, default=24)
    risk_level = Column(String(32), default="LOW")
    created_at = Column(DateTime, default=datetime.utcnow)


class Alert(Base):
    """Real-time alerts for ongoing cyber fraud tracking."""
    __tablename__ = "alerts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id = Column(String(36), ForeignKey("cases.id", ondelete="CASCADE"), nullable=True, index=True)
    address = Column(String(128), nullable=False, index=True)
    chain = Column(String(32), nullable=False)
    alert_type = Column(String(64), nullable=False)  # NEW_TRANSFER, EXCHANGE_DEPOSIT, MIXER_INTERACTION, ASSET_SPLIT
    severity = Column(String(32), default="INFO")  # INFO, WARNING, CRITICAL
    message = Column(Text, nullable=False)
    payload = Column(JSON, nullable=True)
    dispatched = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    case = relationship("Case", back_populates="alerts")


async def init_db() -> None:
    """Initialize database tables."""
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("PostgreSQL database tables initialized successfully.")
    except Exception as exc:
        logger.warning(
            "Could not connect to PostgreSQL database during startup: %s. "
            "Backend will operate in standalone mode if external DB is offline.",
            exc
        )


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency injection yield for FastAPI request context."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
