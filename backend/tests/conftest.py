from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.main import app
from app.modules.calls.router import get_session
from app.modules.calls.schema import Call

BACKEND_DIR = Path(__file__).resolve().parent.parent


@pytest.fixture
def test_db_url(tmp_path, monkeypatch):
    # env.py reads settings.database_url at run time, so the monkeypatch
    # points the migration chain at the throwaway database
    url = f"sqlite+aiosqlite:///{tmp_path / 'test.sqlite3'}"
    monkeypatch.setattr(settings, "database_url", url)
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "app" / "database" / "alembic"))
    command.upgrade(cfg, "head")
    return url


@pytest.fixture
async def test_engine(test_db_url):
    engine = create_async_engine(test_db_url, connect_args={"check_same_thread": False})
    yield engine
    await engine.dispose()


@pytest.fixture
def test_session_factory(test_engine):
    return sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture
async def client(test_session_factory):
    async def override_get_session():
        async with test_session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def make_call(test_session_factory):
    # there is no create endpoint; rows are inserted through the session directly
    async def _make_call(**overrides) -> Call:
        overrides.setdefault("phone_number", "+55 11 99999-0000")
        async with test_session_factory() as session:
            call = Call(**overrides)
            session.add(call)
            await session.commit()
            await session.refresh(call)
            return call

    return _make_call
