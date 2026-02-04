from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


# shared ORM base: models inherit from this so SQLAlchemy knows about their tables
class Base(DeclarativeBase):
    pass


# location of the relational database storing info on users, servers and corpora
DATABASE_URL = "postgresql+asyncpg://middleware_user:middleware_pwd@localhost:5434/middleware_genai"  # TODO move value to .env TODO location depends on where FastAPI is executed

# initialize async DB session
engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


# yield DB session per request
async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
