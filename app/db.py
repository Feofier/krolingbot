from sqlalchemy import URL
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

from .config import DB_URL


class Base(DeclarativeBase):
    pass


def _make_engine():
    if DB_URL.startswith("postgresql"):
        # Neon и любой облачный Postgres требуют TLS; параметры передаём кодом,
        # а не в строке (в строке они нестабильно парсятся разными драйверами)
        url = DB_URL.split("?")[0]
        return create_async_engine(url, echo=False,
                                   connect_args={"ssl": True})
    return create_async_engine(DB_URL, echo=False)


engine = _make_engine()
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncSession:
    async with SessionLocal() as session:
        yield session
