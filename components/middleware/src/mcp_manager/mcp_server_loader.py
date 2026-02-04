
import os
from contextlib import asynccontextmanager
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

DATABASE_URL = os.getenv(
    "MIDDLEWARE_DATABASE_URL",
    "postgresql+asyncpg://middleware_ro:middleware_ro_pwd@localhost:5434/middleware_genai",  # TODO make .env only
)

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
)

SessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession,
)

@asynccontextmanager
async def session_scope() -> AsyncSession:
    async with SessionLocal() as session:
        yield session


async def load_allowed_servers_for_user(username: str):
    async with session_scope() as db:
        result = await db.execute(
            text("""
                SELECT id, name, kind, transport, enabled, config, created_at
                FROM vw_mcp_servers_effective_by_username
                WHERE username = :username
            """),
            {"username": username},
        )
        rows = result.mappings().all()
        return [dict(r) for r in rows]