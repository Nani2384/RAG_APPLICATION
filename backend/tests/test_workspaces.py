import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.domain import User, Workspace

@pytest.mark.asyncio
async def test_workspace_creation_and_listing(client: AsyncClient, db: AsyncSession):
    # 1. Register & login a new user
    reg_res = await client.post("/api/v1/auth/register", json={
        "email": "workspacetest@example.com", "password": "securepassword123"
    })
    assert reg_res.status_code == 201
    
    login_res = await client.post("/api/v1/auth/login", json={
        "email": "workspacetest@example.com", "password": "securepassword123"
    })
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # 2. Get workspaces list (should contain the default seeded workspace)
    get_res1 = await client.get("/api/v1/workspaces/", headers=headers)
    assert get_res1.status_code == 200
    workspaces = get_res1.json()["data"]
    assert len(workspaces) == 1
    assert workspaces[0]["name"] == "My Workspace"
    default_ws_id = workspaces[0]["id"]
    
    # 3. Create a new workspace
    post_res = await client.post("/api/v1/workspaces/", json={"name": "Project Beta"}, headers=headers)
    assert post_res.status_code == 201
    new_ws = post_res.json()
    assert new_ws["name"] == "Project Beta"
    assert new_ws["id"] != default_ws_id
    
    # 4. Get workspaces list again (should contain both)
    get_res2 = await client.get("/api/v1/workspaces/", headers=headers)
    assert get_res2.status_code == 200
    workspaces2 = get_res2.json()["data"]
    assert len(workspaces2) == 2
    names = [ws["name"] for ws in workspaces2]
    assert "My Workspace" in names
    assert "Project Beta" in names

@pytest.mark.asyncio
async def test_workspace_creation_validation(client: AsyncClient):
    # Register & login
    await client.post("/api/v1/auth/register", json={
        "email": "wsvaltest@example.com", "password": "securepassword123"
    })
    login_res = await client.post("/api/v1/auth/login", json={
        "email": "wsvaltest@example.com", "password": "securepassword123"
    })
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Create workspace with empty name
    post_res = await client.post("/api/v1/workspaces/", json={"name": "   "}, headers=headers)
    assert post_res.status_code == 400
    assert "Workspace name cannot be empty" in post_res.json()["detail"]
