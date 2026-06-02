import pytest
import os
import json
from unittest.mock import patch, MagicMock
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.domain import User, Workspace, Document
from app.services.ingestion import IngestionService

@pytest.mark.asyncio
async def test_upload_document_success(client: AsyncClient, db: AsyncSession):
    """Test uploading a document successfully through the API."""
    # 1. Register & Login user
    email = "uploader@example.com"
    await client.post("/api/v1/auth/register", json={"email": email, "password": "securepassword123"})
    login_res = await client.post("/api/v1/auth/login", json={"email": email, "password": "securepassword123"})
    token = login_res.json()["access_token"]
    
    # 2. Upload mock file
    headers = {"Authorization": f"Bearer {token}"}
    files = {"file": ("test_doc.txt", b"This is a testing upload document.", "text/plain")}
    
    # Mock celery task to avoid asyncio.run event loop conflicts
    with patch("app.api.v1.documents.process_document_job.delay") as mock_celery:
        res = await client.post("/api/v1/documents/upload", files=files, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["message"] == "Document uploaded and processing started."
        assert "document_id" in data
        
        # Verify Celery job was queued
        mock_celery.assert_called_once()
        
        # Verify document exists in database
        doc_id = data["document_id"]
        result = await db.execute(select(Document).where(Document.id == doc_id))
        doc = result.scalar_one_or_none()
        assert doc is not None
        assert doc.filename == "test_doc.txt"
        assert doc.status == "uploaded"

@pytest.mark.asyncio
async def test_list_documents(client: AsyncClient, db: AsyncSession):
    """Test listing documents returned are filtered by workspace ownership."""
    # 1. Register and login
    email = "lister@example.com"
    await client.post("/api/v1/auth/register", json={"email": email, "password": "securepassword123"})
    login_res = await client.post("/api/v1/auth/login", json={"email": email, "password": "securepassword123"})
    token = login_res.json()["access_token"]

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one()
    ws_result = await db.execute(select(Workspace).where(Workspace.owner_id == user.id))
    workspace = ws_result.scalar_one()

    # Seed mock document in database
    doc = Document(filename="test_list.txt", file_path="/tmp/test_list.txt", workspace_id=workspace.id, status="indexed")
    db.add(doc)
    await db.commit()

    # Get documents list
    headers = {"Authorization": f"Bearer {token}"}
    res = await client.get("/api/v1/documents/", headers=headers)
    assert res.status_code == 200
    data = res.json()["data"]
    assert len(data) == 1
    assert data[0]["filename"] == "test_list.txt"
    assert data[0]["status"] == "indexed"

@pytest.mark.asyncio
async def test_retry_document_ingestion_success(client: AsyncClient, db: AsyncSession):
    """Test manually re-triggering ingestion for a document in error status."""
    email = "retryer@example.com"
    await client.post("/api/v1/auth/register", json={"email": email, "password": "securepassword123"})
    login_res = await client.post("/api/v1/auth/login", json={"email": email, "password": "securepassword123"})
    token = login_res.json()["access_token"]

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one()
    ws_result = await db.execute(select(Workspace).where(Workspace.owner_id == user.id))
    workspace = ws_result.scalar_one()

    # Seed failed document
    doc = Document(
        filename="failed_doc.txt",
        file_path="/tmp/failed_doc.txt",
        workspace_id=workspace.id,
        status="error",
        metadata_json=json.dumps({"error": "Transient embedding error"})
    )
    db.add(doc)
    await db.commit()

    headers = {"Authorization": f"Bearer {token}"}
    with patch("app.api.v1.documents.process_document_job.delay") as mock_celery:
        res = await client.post(f"/api/v1/documents/{doc.id}/retry", headers=headers)
        assert res.status_code == 200
        assert "manually re-triggered" in res.json()["message"]
        
        # Verify task was re-queued
        mock_celery.assert_called_once_with(doc.id, "/tmp/failed_doc.txt")
        
        # Verify status reset to processing
        await db.refresh(doc)
        assert doc.status == "processing"

def test_ingestion_service_parsing(tmp_path):
    """Test IngestionService end-to-end local text file parsing and indexing."""
    # Create temp text file
    test_file = tmp_path / "sample.txt"
    test_file.write_text("Hello. This is automated parsing validation text.")
    
    # Run ingestion
    service = IngestionService()
    vector_ids = service.process_document(str(test_file), document_id=10, workspace_id=1)
    
    # Verify mock vectors inserted
    assert len(vector_ids) > 0
    assert len(vector_ids[0]) == 36  # should be UUID
