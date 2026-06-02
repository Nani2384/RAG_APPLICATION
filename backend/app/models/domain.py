from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    workspaces = relationship("Workspace", back_populates="owner")

class Workspace(Base):
    __tablename__ = "workspaces"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    owner = relationship("User", back_populates="workspaces")
    documents = relationship("Document", back_populates="workspace")

class Document(Base):
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"))
    filename = Column(String, nullable=False)
    file_path = Column(String)  # local path or S3 key
    status = Column(String, default="uploaded") # uploaded, processing, indexed, error
    metadata_json = Column(Text) # Additional JSON metadata
    vector_ids = Column(Text) # Mapped vector IDs in Pinecone/FAISS
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    workspace = relationship("Workspace", back_populates="documents")

class ChatThread(Base):
    __tablename__ = "chat_threads"
    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"))
    title = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    messages = relationship("Message", back_populates="thread")

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    thread_id = Column(Integer, ForeignKey("chat_threads.id"))
    role = Column(String, nullable=False) # user or assistant or system
    content = Column(Text, nullable=False)
    sources = Column(Text) # JSON serialized list of source chunks
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    thread = relationship("ChatThread", back_populates="messages")
