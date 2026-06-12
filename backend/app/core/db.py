from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings


def create_engine_and_session_factory(url: str) -> tuple[AsyncEngine, sessionmaker]:
    engine = create_async_engine(
        url,
        echo=False,
        connect_args={"check_same_thread": False},
    )
    session_factory = sessionmaker(  # type: ignore[call-overload]
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    return engine, session_factory


engine, async_session = create_engine_and_session_factory(settings.database_url)
