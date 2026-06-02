import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.domain import User, Workspace

@pytest.mark.asyncio
async def test_register_success(client: AsyncClient, db: AsyncSession):
    """Test successful user registration and automatic workspace seeding."""
    email = "newuser@example.com"
    payload = {"email": email, "password": "securepassword123"}
    
    res = await client.post("/api/v1/auth/register", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["message"] == "User registered successfully."
    assert "user_id" in data

    # Verify user exists in test DB
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    assert user is not None
    assert user.email == email
    
    # Verify default workspace was automatically seeded
    ws_result = await db.execute(select(Workspace).where(Workspace.owner_id == user.id))
    workspace = ws_result.scalar_one_or_none()
    assert workspace is not None
    assert workspace.name == "My Workspace"

@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient, db: AsyncSession):
    """Test registration fails when using a duplicate email address."""
    email = "dupuser@example.com"
    payload = {"email": email, "password": "securepassword123"}
    
    # Register first time
    res = await client.post("/api/v1/auth/register", json=payload)
    assert res.status_code == 201

    # Register second time
    res_dup = await client.post("/api/v1/auth/register", json=payload)
    assert res_dup.status_code == 400
    assert "already exists" in res_dup.json()["detail"]

@pytest.mark.asyncio
async def test_register_password_too_short(client: AsyncClient):
    """Test registration blocks passwords shorter than 8 characters."""
    payload = {"email": "short@example.com", "password": "short"}
    res = await client.post("/api/v1/auth/register", json=payload)
    assert res.status_code == 400
    assert "at least 8 characters" in res.json()["detail"]

@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, db: AsyncSession):
    """Test successful user login and access token retrieval."""
    email = "loginuser@example.com"
    password = "securepassword123"
    
    # Register first
    await client.post("/api/v1/auth/register", json={"email": email, "password": password})
    
    # Login
    res = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

@pytest.mark.asyncio
async def test_login_invalid_credentials(client: AsyncClient):
    """Test login blocks access on invalid credentials."""
    payload = {"email": "invalid@example.com", "password": "wrongpassword"}
    res = await client.post("/api/v1/auth/login", json=payload)
    assert res.status_code == 401
    assert "Invalid email or password" in res.json()["detail"]

@pytest.mark.asyncio
async def test_get_current_user_secure(client: AsyncClient, db: AsyncSession):
    """Test JWT validation in protected dependency routes."""
    email = "jwtuser@example.com"
    password = "securepassword123"
    
    # Register and get token
    await client.post("/api/v1/auth/register", json={"email": email, "password": password})
    login_res = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    token = login_res.json()["access_token"]
    
    # Call protected endpoint (list workspaces)
    headers = {"Authorization": f"Bearer {token}"}
    res = await client.get("/api/v1/documents/", headers=headers)
    assert res.status_code == 200

@pytest.mark.asyncio
async def test_get_current_user_bypass(client: AsyncClient, db: AsyncSession):
    """Test development dummy-token bypass fallback."""
    # Seed default user with ID 1 (required by bypass handler)
    from app.core.security import get_password_hash
    admin = User(id=1, email="admin@ragplatform.com", hashed_password=get_password_hash("admin123"))
    db.add(admin)
    ws = Workspace(id=1, name="Default Workspace", owner_id=1)
    db.add(ws)
    await db.commit()

    headers = {"Authorization": "Bearer dummy-token-123"}
    res = await client.get("/api/v1/documents/", headers=headers)
    assert res.status_code == 200
