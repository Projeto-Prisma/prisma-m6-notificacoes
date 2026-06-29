from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .config import get_settings
from .models import Base

logger = logging.getLogger("m6.db")

cfg = get_settings()
engine = create_async_engine(cfg.database_url, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def criar_tabelas() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Adiciona coluna lida se a tabela já existia antes desta versão (idempotente)
        await conn.execute(
            text("ALTER TABLE notificacoes ADD COLUMN IF NOT EXISTS lida BOOLEAN NOT NULL DEFAULT false")
        )
    logger.info("Tabelas verificadas/criadas.")


async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
