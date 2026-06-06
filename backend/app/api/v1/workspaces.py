from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel
from typing import List, Dict, Any

from app.api.v1.auth import get_current_user
from app.core.database import get_db
from app.models.domain import Workspace

router = APIRouter()

class WorkspaceCreate(BaseModel):
    name: str

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_workspace(
    request: WorkspaceCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if not request.name.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Workspace name cannot be empty."
        )
    
    workspace = Workspace(name=request.name.strip(), owner_id=current_user["id"])
    db.add(workspace)
    await db.commit()
    await db.refresh(workspace)
    return {
        "id": workspace.id,
        "name": workspace.name,
        "owner_id": workspace.owner_id,
        "created_at": workspace.created_at.isoformat() if workspace.created_at else None
    }

@router.get("/")
async def list_workspaces(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Workspace)
        .where(Workspace.owner_id == current_user["id"])
        .order_by(Workspace.created_at.asc())
    )
    workspaces = result.scalars().all()
    return {
        "data": [
            {
                "id": ws.id,
                "name": ws.name,
                "created_at": ws.created_at.isoformat() if ws.created_at else None
            }
            for ws in workspaces
        ]
    }
