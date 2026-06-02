import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.domain import User, Workspace

@pytest.mark.asyncio
async def test_workspace_isolation_completions(client: AsyncClient, db: AsyncSession):
    """Test that User B cannot request chat completions on User A's workspace."""
    # 1. Register User A
    res_a = await client.post("/api/v1/auth/register", json={
        "email": "usera@example.com", "password": "securepassword123"
    })
    assert res_a.status_code == 201
    
    # 2. Register User B & login to obtain token
    res_b = await client.post("/api/v1/auth/register", json={
        "email": "userb@example.com", "password": "securepassword123"
    })
    assert res_b.status_code == 201
    
    login_b = await client.post("/api/v1/auth/login", json={
        "email": "userb@example.com", "password": "securepassword123"
    })
    token_b = login_b.json()["access_token"]
    
    # 3. Retrieve Workspace ID of User A from DB
    result_a = await db.execute(select(User).where(User.email == "usera@example.com"))
    user_a = result_a.scalar_one()
    ws_result_a = await db.execute(select(Workspace).where(Workspace.owner_id == user_a.id))
    workspace_a = ws_result_a.scalar_one()
    
    # 4. Request completions using User B's token targeting User A's Workspace
    headers = {"Authorization": f"Bearer {token_b}"}
    payload = {
        "query": "Hello",
        "workspace_id": workspace_a.id,
        "chat_history": []
    }
    
    res_malicious = await client.post("/api/v1/chat/completions", json=payload, headers=headers)
    assert res_malicious.status_code == 403
    assert "Access denied" in res_malicious.json()["detail"]

@pytest.mark.asyncio
async def test_workspace_isolation_documents(client: AsyncClient, db: AsyncSession):
    """Test that User B listing documents only sees their own files."""
    # 1. Register & Login User A
    await client.post("/api/v1/auth/register", json={
        "email": "usera@example.com", "password": "securepassword123"
    })
    login_a = await client.post("/api/v1/auth/login", json={
        "email": "usera@example.com", "password": "securepassword123"
    })
    token_a = login_a.json()["access_token"]
    
    # 2. Register & Login User B
    await client.post("/api/v1/auth/register", json={
        "email": "userb@example.com", "password": "securepassword123"
    })
    login_b = await client.post("/api/v1/auth/login", json={
        "email": "userb@example.com", "password": "securepassword123"
    })
    token_b = login_b.json()["access_token"]

    # 3. Upload file for User A
    from app.models.domain import Document
    result_a = await db.execute(select(User).where(User.email == "usera@example.com"))
    user_a = result_a.scalar_one()
    ws_result_a = await db.execute(select(Workspace).where(Workspace.owner_id == user_a.id))
    workspace_a = ws_result_a.scalar_one()
    
    doc_a = Document(filename="usera_secret.txt", file_path="/tmp/a.txt", workspace_id=workspace_a.id, status="indexed")
    db.add(doc_a)
    await db.commit()

    # 4. User B requests documents list
    headers_b = {"Authorization": f"Bearer {token_b}"}
    res_b = await client.get("/api/v1/documents/", headers=headers_b)
    assert res_b.status_code == 200
    docs_b = res_b.json()["data"]
    
    # User B should see zero documents because User A's file is isolated
    assert len(docs_b) == 0
    
    # 5. User A requests documents list
    headers_a = {"Authorization": f"Bearer {token_a}"}
    res_a = await client.get("/api/v1/documents/", headers=headers_a)
    assert res_a.status_code == 200
    docs_a = res_a.json()["data"]
    assert len(docs_a) == 1
    assert docs_a[0]["filename"] == "usera_secret.txt"
