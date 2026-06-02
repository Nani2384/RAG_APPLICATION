from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Optional
import json

from app.api.v1.auth import get_current_user
from app.rag.generators.generator import RAGGenerator
from app.rag.retrievers.retriever import RAGRetriever
from app.rag.vector_stores.faiss_store import FAISSVectorStore
from app.rag.vector_stores.pinecone_store import PineconeVectorStore
from app.rag.embeddings.openai_embedder import OpenAIEmbedder
from app.core.config import settings
from app.core.database import get_db, AsyncSessionLocal
from app.models.domain import ChatThread, Message, Workspace
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

router = APIRouter()

class ChatRequest(BaseModel):
    query: str
    workspace_id: int
    thread_id: Optional[int] = None
    chat_history: List[Dict[str, str]] = []

def get_retriever():
    embedder = OpenAIEmbedder()
    if settings.VECTOR_STORE_TYPE == "pinecone":
        store = PineconeVectorStore(embedder)
    else:
        store = FAISSVectorStore(embedder)
        
    return RAGRetriever(vector_store=store)

async def save_assistant_message(thread_id: int, content: str, sources_chunks: list):
    async with AsyncSessionLocal() as session:
        assistant_msg = Message(
            thread_id=thread_id,
            role="assistant",
            content=content,
            sources=json.dumps(sources_chunks)
        )
        session.add(assistant_msg)
        await session.commit()
    
from fastapi import HTTPException, status

async def validate_workspace_access(workspace_id: int, user_id: int, db: AsyncSession) -> Workspace:
    result = await db.execute(
        select(Workspace).where(Workspace.id == workspace_id, Workspace.owner_id == user_id)
    )
    ws = result.scalar_one_or_none()
    if not ws:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to requested workspace."
        )
    return ws

@router.post("/completions")
async def chat_completion(
    request: ChatRequest,
    current_user: dict = Depends(get_current_user),
    retriever: RAGRetriever = Depends(get_retriever),
    db: AsyncSession = Depends(get_db)
):
    generator = RAGGenerator()
    
    # 1. Enforce strict workspace ownership isolation
    await validate_workspace_access(request.workspace_id, current_user["id"], db)
    
    # 2. Enforce thread ownership isolation if provided
    thread_id = request.thread_id
    if thread_id:
        result = await db.execute(
            select(ChatThread)
            .join(Workspace)
            .where(ChatThread.id == thread_id, Workspace.owner_id == current_user["id"])
        )
        thread = result.scalar_one_or_none()
        if not thread:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to requested chat thread."
            )
            
    # 3. Retrieve the context
    context_chunks = retriever.retrieve(query=request.query, workspace_id=request.workspace_id)
    
    # 4. Get or create thread
    if not thread_id:
        thread = ChatThread(workspace_id=request.workspace_id, title=request.query[:40] + "...")
        db.add(thread)
        await db.commit()
        await db.refresh(thread)
        thread_id = thread.id
        
    # 5. Save User Message
    user_msg = Message(thread_id=thread_id, role="user", content=request.query)
    db.add(user_msg)
    await db.commit()
    
    # 6. Generate and stream with interception to save the assistant's reply
    async def wrapper_generator():
        accumulated_text = ""
        # Yield the thread_id first so client can update active thread context
        yield f"data: {json.dumps({'type': 'thread_id', 'data': thread_id})}\n\n"
        
        async for chunk in generator.generate_streaming(
            query=request.query, 
            context_chunks=context_chunks,
            chat_history=request.chat_history
        ):
            yield chunk
            # Extract content from chunk payload
            if chunk.startswith("data: "):
                data_str = chunk[6:].strip()
                if data_str != "[DONE]" and not data_str.startswith("error"):
                    try:
                        parsed = json.loads(data_str)
                        if parsed.get("type") == "content":
                            accumulated_text += parsed.get("data", "")
                    except Exception:
                        pass
        
        if accumulated_text:
            await save_assistant_message(thread_id, accumulated_text, context_chunks)
            
    return StreamingResponse(
        wrapper_generator(),
        media_type="text/event-stream"
    )

@router.get("/threads")
async def list_threads(
    workspace_id: int = Query(..., description="Workspace ID to filter threads"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Enforce strict workspace ownership isolation
    await validate_workspace_access(workspace_id, current_user["id"], db)
    
    result = await db.execute(
        select(ChatThread)
        .where(ChatThread.workspace_id == workspace_id)
        .order_by(ChatThread.created_at.desc())
    )
    threads = result.scalars().all()
    return {
        "data": [
            {
                "id": t.id,
                "title": t.title,
                "created_at": t.created_at.isoformat() if t.created_at else None
            }
            for t in threads
        ]
    }

@router.get("/threads/{thread_id}/messages")
async def get_thread_messages(
    thread_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Enforce strict thread owner verification to prevent message sniffing
    result = await db.execute(
        select(Message)
        .join(ChatThread)
        .join(Workspace)
        .where(Message.thread_id == thread_id, Workspace.owner_id == current_user["id"])
        .order_by(Message.created_at.asc())
    )
    messages = result.scalars().all()
    
    # If no messages found, check if thread exists at all and is owned
    if not messages:
        thread_check = await db.execute(
            select(ChatThread)
            .join(Workspace)
            .where(ChatThread.id == thread_id, Workspace.owner_id == current_user["id"])
        )
        if not thread_check.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to requested chat thread."
            )
            
    return {
        "data": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "sources": json.loads(m.sources) if m.sources else [],
                "created_at": m.created_at.isoformat() if m.created_at else None
            }
            for m in messages
        ]
    }
