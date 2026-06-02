# Bugs and Missing Features

This document tracks unresolved items, minor missing functionalities, and production-hardening steps for the Enterprise Multimodal RAG Application.

---

## 🚨 Critical Blockers Status: **ALL RESOLVED**

All Phase 1 critical blocks have been resolved and verified:
1. **FAISS isolation bug** ➡️ **RESOLVED** (FAISS index moved to persistent, shared `/app/storage/faiss_index` volume).
2. **Workspace ID metadata mismatch** ➡️ **RESOLVED** (Ingestion service now appends `workspace_id` directly to vector metadata).
3. **DATABASE_URL config interpolation** ➡️ **RESOLVED** (Settings class dynamic constructor automatically assembles async DB url from credentials).
4. **Database Table creation** ➡️ **RESOLVED** (FastAPI startup handler executes `conn.run_sync(Base.metadata.create_all)` on boot).
5. **Sync-Async Ingestion status sync** ➡️ **RESOLVED** (Celery worker task executes async status transitions inside PostgreSQL via `asyncio.run()`).

---

## ⚠️ Minor Missing Features (For Production Hardening)

### 1. Robust JWT User Authentication
- **Current State**: Authentication routes inside `auth.py` are mocked.
  - The login API returns a static dummy token (`dummy-token-123`).
  - The `get_current_user` dependency accepts any token and returns a dummy `admin` payload.
- **Production Need**: Replace with a secure JWT authentication flow. Implement password hashing using `bcrypt` and verify signatures against actual user rows in PostgreSQL.

### 2. Vector Store Deletion Hooks
- **Current State**: Deleting a document from PostgreSQL does not automatically remove the indexed vector chunks from FAISS or Pinecone.
  - The deletion hooks in `faiss_store.py` and `pinecone_store.py` are currently stubbed or operate independently.
- **Production Need**: Wire up document delete API hooks that retrieve the mapped `vector_ids` and call the vector database's `delete_by_ids` methods to clear out orphan data.

### 3. Frontend Workspace Selector APIs
- **Current State**: The UI allows users to create workspaces or click the item, but workspace IDs are hardcoded to `1` behind the scenes during chat completion and document uploads.
- **Production Need**: Build complete backend controllers (`POST /workspaces`, `GET /workspaces`) and add a workspace switcher dropdown to the Sidebar so files and chats can be segregated into multiple client zones.

### 4. Advanced Frontend Visual Polish
- **Current State**: Markdown citations, loading indicators, and page transitions are functional.
- **Production Need**:
  - Add standard markdown-code syntax highlighting for code blocks inside messages.
  - Integrate visual transition animations using `framer-motion` when switching between active side panels or loading historical chats.
