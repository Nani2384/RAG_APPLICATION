import pytest
import os
import json
from unittest.mock import patch, MagicMock
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.domain import User, Workspace, Document

@pytest.mark.asyncio
async def test_cascading_document_deletion_success(client: AsyncClient, db: AsyncSession, tmp_path):
    """Test that deleting a document sweeps PostgreSQL, removes files, and cleans FAISS."""
    # 1. Register & Login user
    email = "deleter@example.com"
    await client.post("/api/v1/auth/register", json={"email": email, "password": "securepassword123"})
    login_res = await client.post("/api/v1/auth/login", json={"email": email, "password": "securepassword123"})
    token = login_res.json()["access_token"]
    
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one()
    ws_result = await db.execute(select(Workspace).where(Workspace.owner_id == user.id))
    workspace = ws_result.scalar_one()

    # 2. Seed mock physical file on disk
    mock_file = tmp_path / "delete_target.txt"
    mock_file.write_text("Deleting this file during verification.")
    assert os.path.exists(str(mock_file))

    # 3. Seed mock document with vector IDs in database
    vector_ids = ["vector-uuid-1111", "vector-uuid-2222"]
    doc = Document(
        filename="delete_target.txt",
        file_path=str(mock_file),
        workspace_id=workspace.id,
        status="indexed",
        vector_ids=json.dumps(vector_ids)
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    doc_id = doc.id

    # 4. Perform DELETE request with auth headers
    headers = {"Authorization": f"Bearer {token}"}
    
    # Mock FAISS Vector store delete_by_ids to prevent loading real large files
    with patch("app.api.v1.documents.FAISSVectorStore.delete_by_ids") as mock_faiss_delete:
        res = await client.delete(f"/api/v1/documents/{doc_id}", headers=headers)
        assert res.status_code == 200
        assert res.json()["message"] == "Document deleted successfully."
        
        # Verify FAISS delete was synchronized with the identical vector IDs
        mock_faiss_delete.assert_called_once_with(vector_ids)

    # 5. Verify local physical file was removed from the disk
    assert not os.path.exists(str(mock_file))

    # 6. Verify document was swept from database
    db_result = await db.execute(select(Document).where(Document.id == doc_id))
    deleted_doc = db_result.scalar_one_or_none()
    assert deleted_doc is None
