import asyncio

from passlib.context import CryptContext
from sqlalchemy import select

from components.gateway.app.db.session import AsyncSessionLocal, engine, Base
from components.gateway.app.db.models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "adminpass"
ADMIN_ROLE = "admin"


async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        res = await db.execute(select(User).where(User.username == ADMIN_USERNAME))
        existing = res.scalar_one_or_none()
        if existing:
            print("Admin already exists:", existing.username)
            return

        user = User(
            username=ADMIN_USERNAME,
            password_hash=pwd_context.hash(ADMIN_PASSWORD),
            role=ADMIN_ROLE,
        )
        db.add(user)
        await db.commit()
        print("Created admin:", ADMIN_USERNAME, "password:", ADMIN_PASSWORD)


if __name__ == "__main__":
    asyncio.run(main())
