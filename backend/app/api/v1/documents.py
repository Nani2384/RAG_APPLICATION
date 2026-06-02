from fastapi import APIRouter, File, UploadFile, Depends, HTTPException, status, Form
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, Optional
import os
import aiofiles
import json
from sqlalchemy.future import select
import structlog

from app.api.v1.auth import get_current_user
from app.core.database import get_db
from app.core.config import settings
from app.worker import process_document_job
from app.models.domain import Document, Workspace
from app.rag.vector_stores.faiss_store import FAISSVectorStore
from app.rag.embeddings.openai_embedder import OpenAIEmbedder

router = APIRouter()
logger = structlog.get_logger(__name__)

async def validate_workspace_ownership(workspace_id: int, user_id: int, db: AsyncSession) -> Workspace:
    """Verifies if the workspace exists and belongs to the authenticated user."""
    result = await db.execute(
        select(Workspace).where(Workspace.id == workspace_id, Workspace.owner_id == user_id)
    )
    workspace = workspace_result = result.scalar_one_or_none()
    if not workspace:
        logger.warn("Security violation: unauthorized workspace access attempt", user_id=user_id, workspace_id=workspace_id)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to requested workspace."
        )
    return workspace

@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    workspace_id: Optional[int] = Form(1),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    logger.info("Upload request received", filename=file.filename, user_id=current_user["id"])
    
    # Secure Workspace Routing: If user doesn't own workspace_id (or default 1), route to their first workspace
    result = await db.execute(
        select(Workspace).where(Workspace.id == workspace_id, Workspace.owner_id == current_user["id"])
    )
    ws = result.scalar_one_or_none()
    if not ws:
        result = await db.execute(select(Workspace).where(Workspace.owner_id == current_user["id"]))
        ws = result.scalar_one_or_none()
        if not ws:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No active workspace found for this account."
            )
        workspace_id = ws.id
        
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    file_path = os.path.join(settings.UPLOAD_DIR, f"{current_user['id']}_{file.filename}")
    
    async with aiofiles.open(file_path, 'wb') as out_file:
        content = await file.read()
        await out_file.write(content)

    doc = Document(filename=file.filename, file_path=file_path, workspace_id=workspace_id, status="uploaded")
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    
    # Trigger Celery Background Processing
    process_document_job.delay(doc.id, file_path)
    
    logger.info("Document upload succeeded, Celery ingestion task queued", document_id=doc.id, user_id=current_user["id"])
    return {"message": "Document uploaded and processing started.", "document_id": doc.id}

@router.get("/")
async def list_documents(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Enforce strict multi-user isolation: fetch only documents in workspaces owned by user
    result = await db.execute(
        select(Document)
        .join(Workspace)
        .where(Workspace.owner_id == current_user["id"])
        .order_by(Document.id.desc())
    )
    documents = result.scalars().all()
    return {
        "data": [
            {
                "id": doc.id,
                "filename": doc.filename,
                "status": doc.status,
                "workspace_id": doc.workspace_id,
                "metadata_json": doc.metadata_json,
                "created_at": doc.created_at.isoformat() if doc.created_at else None
            }
            for doc in documents
        ]
    }

@router.post("/{document_id}/retry")
async def retry_document_ingestion(
    document_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    # Enforce strict multi-user isolation: verify ownership of the document's workspace
    result = await db.execute(
        select(Document)
        .join(Workspace)
        .where(Document.id == document_id, Workspace.owner_id == current_user["id"])
    )
    doc = result.scalars().first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
        
    if doc.status != "error":
        raise HTTPException(status_code=400, detail="Only documents in error status can be retried.")
        
    # Reset status and retry count
    doc.status = "processing"
    doc.metadata_json = json.dumps({"manual_retry": True})
    await db.commit()
    
    # Re-trigger Celery task
    process_document_job.delay(doc.id, doc.file_path)
    
    logger.info("Manual ingestion retry triggered successfully", document_id=doc.id, user_id=current_user["id"])
    return {"message": "Document ingestion manually re-triggered successfully.", "document_id": doc.id}

@router.delete("/{document_id}")
async def delete_document(
    document_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    logger.info("Delete document request received", document_id=document_id, user_id=current_user["id"])
    
    # Enforce strict multi-user isolation: verify workspace ownership
    result = await db.execute(
        select(Document)
        .join(Workspace)
        .where(Document.id == document_id, Workspace.owner_id == current_user["id"])
    )
    doc = result.scalars().first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found or access denied.")
        
    # 1. Sync deletion with FAISS Vector Store
    vector_ids_str = doc.vector_ids
    if vector_ids_str:
        try:
            vector_ids = json.loads(vector_ids_str)
            if vector_ids:
                embedder = OpenAIEmbedder()
                vector_store = FAISSVectorStore(embedder)
                vector_store.delete_by_ids(vector_ids)
                logger.info("Synchronized vector deletions inside FAISS", vector_ids=vector_ids)
        except Exception as err:
            logger.error("Failed to synchronize vector deletion inside FAISS", error=str(err))
            
    # 2. Delete local physical file from disk storage to prevent space leaks
    if doc.file_path and os.path.exists(doc.file_path):
        try:
            os.remove(doc.file_path)
            logger.info("Physical file deleted from disk storage", file_path=doc.file_path)
        except Exception as err:
            logger.error("Failed to delete physical file from storage", error=str(err))
            
    # 3. Remove document from database
    await db.delete(doc)
    await db.commit()
    
    logger.info("Document deleted successfully from SQL database", document_id=document_id, user_id=current_user["id"])
    return {"message": "Document deleted successfully.", "document_id": document_id}
