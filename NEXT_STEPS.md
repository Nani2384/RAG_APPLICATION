# Next Steps & Development Roadmap

This document outlines the next stages of development for the Enterprise Multimodal RAG Application now that the end-to-end alignment and dashboard are operational.

---

## 🎯 Recommended Next Milestone: "Production Hardening & Multi-tenancy"

Now that local uploading, parsing, Celery background indexing, and streaming chat persistence are working, we can transition the project from a local MVP into a production-ready, multi-tenant platform.

### Step 1: Implement JWT Authentication
1. **User Database Expansion**:
   - Update `User` model to support full registration parameters.
   - Install `passlib[bcrypt]` and `python-jose` dependencies in the environment.
2. **Token Flow**:
   - Implement real user credential checking in `auth.py` and password hashing on registration.
   - Issue signed HS256 JWT tokens upon `/login`.
   - Update `get_current_user` to decode the token, check expiration, and retrieve the user row from PostgreSQL.

### Step 2: Enable True Workspace Isolation
1. **Workspaces API**:
   - Implement backend routes to list, create, and delete workspaces (`/api/v1/workspaces/`).
2. **Dynamic UI Switcher**:
   - Add a workspace selector to the Next.js Sidebar.
   - Store the active workspace ID in React state, and substitute it instead of the hardcoded `workspace_id: 1` inside chat queries and document uploads.

### Step 3: Complete Deletion Hooks
1. **Sync Deletes**:
   - Update backend `/api/v1/documents/{id}` deletion endpoint.
   - When a document is removed, fetch its database record, extract the JSON `vector_ids`, and invoke `vector_store.delete_by_ids(vector_ids)` to clear orphan chunks from FAISS or Pinecone.

### Step 4: UI Polish & Enhancements
1. **Markdown Formatting**:
   - Add code block syntax highlighting using a library like `react-syntax-highlighter` inside `ChatInterface.tsx`.
2. **Smooth Transitions**:
   - Integrate `framer-motion` to fade in new messages and slide open active side views when switching between tabs.
