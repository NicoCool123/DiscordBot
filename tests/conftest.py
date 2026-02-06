"""Test configuration and shared fixtures."""

import asyncio
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from api.core.database import Base, get_db
from api.core.jwt_handler import create_access_token
from api.core.security import get_password_hash
from api.models.role import DEFAULT_ROLES, Role
from api.models.user import User

# SQLite in-memory for fast tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def engine():
    """Create a test database engine."""
    test_engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False},
    )

    # SQLite doesn't support JSONB, so we need to handle this via the dialect
    # Register a listener to enable WAL mode and foreign keys for SQLite
    @event.listens_for(test_engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield test_engine

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await test_engine.dispose()


@pytest_asyncio.fixture
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a database session for each test."""
    async_session = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def app(db_session):
    """Create a test FastAPI application."""
    # Import here to avoid circular imports and settings initialization issues
    import os

    # Set required env vars for settings
    os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-key-for-testing-only")
    os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing-only")
    os.environ.setdefault("BOT_API_KEY", "test-bot-api-key")
    os.environ.setdefault("DATABASE_URL", TEST_DATABASE_URL)
    os.environ.setdefault("DEBUG", "true")

    from api.main import app as fastapi_app

    # Override the database dependency
    async def override_get_db():
        yield db_session

    fastapi_app.dependency_overrides[get_db] = override_get_db
    yield fastapi_app
    fastapi_app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    """Create an async HTTP client for testing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def test_user(db_session) -> User:
    """Create a test user."""
    user = User(
        username="testuser",
        email="test@example.com",
        password_hash=get_password_hash("TestPassword123"),
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_admin(db_session) -> User:
    """Create a test admin user."""
    admin = User(
        username="testadmin",
        email="admin@example.com",
        password_hash=get_password_hash("AdminPassword123"),
        is_active=True,
        is_superuser=True,
        is_verified=True,
    )
    db_session.add(admin)
    await db_session.commit()
    await db_session.refresh(admin)
    return admin


@pytest_asyncio.fixture
async def test_roles(db_session) -> list[Role]:
    """Create default roles."""
    roles = []
    for role_data in DEFAULT_ROLES:
        role = Role(
            name=role_data["name"],
            description=role_data["description"],
            permissions=role_data["permissions"],
        )
        db_session.add(role)
        roles.append(role)
    await db_session.commit()
    for role in roles:
        await db_session.refresh(role)
    return roles


@pytest_asyncio.fixture
async def user_token(test_user) -> str:
    """Create a JWT token for the test user."""
    return create_access_token(test_user.id)


@pytest_asyncio.fixture
async def admin_token(test_admin) -> str:
    """Create a JWT token for the test admin."""
    return create_access_token(test_admin.id)


@pytest_asyncio.fixture
def auth_headers(user_token) -> dict:
    """Create authorization headers for the test user."""
    return {"Authorization": f"Bearer {user_token}"}


@pytest_asyncio.fixture
def admin_headers(admin_token) -> dict:
    """Create authorization headers for the test admin."""
    return {"Authorization": f"Bearer {admin_token}"}


@pytest_asyncio.fixture
def bot_headers() -> dict:
    """Create authorization headers for the bot API key."""
    return {"X-API-Key": "test-bot-api-key"}
