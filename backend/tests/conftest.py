import asyncio
import os
import sys
from typing import AsyncGenerator, Generator

# 1. Force testing environment variables before importing core modules
os.environ["TESTING"] = "true"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:////tmp/test.db"
os.environ["UPLOAD_DIR"] = "/tmp/test_uploads"
os.environ["VECTOR_STORE_TYPE"] = "faiss"
os.environ["SECRET_KEY"] = "test-secret-key-very-secure-12345"

# Add application directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from unittest.mock import MagicMock, patch

from app.main import app
from app.core.config import settings
from app.core.database import get_db
from app.models.domain import Base

# Ensure test upload folder exists
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

# 2. Create Async Test Engine using high-speed SQLite
test_engine = create_async_engine(settings.DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False
)

@pytest.fixture(scope="session", autouse=True)
def setup_db():
    """Initializes tables in the isolated SQLite test database before the test session starts."""
    async def init_schema():
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

    async def cleanup_schema():
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await test_engine.dispose()
        if os.path.exists("/tmp/test.db"):
            try:
                os.remove("/tmp/test.db")
            except Exception:
                pass

    # Execute asynchronously inside single one-off event loops
    asyncio.run(init_schema())
    
    yield
    
    asyncio.run(cleanup_schema())

@pytest_asyncio.fixture
async def db() -> AsyncGenerator[AsyncSession, None]:
    """Yields an isolated transactional session for testing, overriding the global get_db with fresh sessions."""
    # Override standard get_db dependency to yield fresh sessions from our pool for each request
    async def override_get_db():
        async with TestSessionLocal() as session:
            try:
                yield session
            finally:
                await session.close()
            
    app.dependency_overrides[get_db] = override_get_db
    
    # Yield a separate test session for verifying database mutations in tests
    async with TestSessionLocal() as test_session:
        yield test_session
        
    # Clean up database records after test using a clean connection outside the session pool
    async with test_engine.begin() as conn:
        await conn.execute(text("DELETE FROM messages;"))
        await conn.execute(text("DELETE FROM chat_threads;"))
        await conn.execute(text("DELETE FROM documents;"))
        await conn.execute(text("DELETE FROM workspaces;"))
        await conn.execute(text("DELETE FROM users;"))
            
    app.dependency_overrides.pop(get_db, None)

@pytest_asyncio.fixture
async def client(db) -> AsyncGenerator[AsyncClient, None]:
    """Yields an HTTPX AsyncClient for FastAPI endpoint testing."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

@pytest.fixture(autouse=True)
def mock_embeddings():
    """Mocks OpenAIEmbedder calls to avoid hitting OpenAI API during tests."""
    with patch("app.rag.embeddings.openai_embedder.OpenAIEmbedder.embed_documents") as mock_embeds, \
         patch("app.rag.embeddings.openai_embedder.OpenAIEmbedder.embed_query") as mock_query:
         
         # Mock embed_documents to return lists of float mock vectors
         mock_embeds.return_value = [[0.1] * 1536]
         mock_query.return_value = [0.1] * 1536
         yield mock_embeds, mock_query

@pytest.fixture(autouse=True)
def eager_celery():
    """Forces Celery tasks to execute synchronously in the test thread."""
    from app.worker import celery_app
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True
    yield
