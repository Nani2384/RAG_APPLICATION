# Production Readiness Checklist

This checklist tracks the engineering tasks required to move the Enterprise Multimodal RAG Application from Phase 1 Local Mock status to a secure, scalable production environment.

---

## 🔐 1. Authentication & Security Hardening
- [x] **Secure JWT Implementation**:
  - Replace the current mock login endpoint and standard token bypass scheme (`get_current_user` in `auth.py`) with a complete OAuth2 JSON Web Token (JWT) flow.
  - Implement actual password hashing using `bcrypt` and verify signatures against actual user rows in PostgreSQL on the `users` table.
- [ ] **Secret Key Rotation**:
  - Move the `SECRET_KEY` in `.env` from static values to a high-entropy secret loaded dynamically from a cloud secret manager (e.g. AWS Secrets Manager or GCP Secret Manager).
- [x] **CORS Settings Hardening**:
  - Restrict `allow_origins=["*"]` inside `backend/app/main.py` to settings whitelisted origins (whitelisted default to `http://localhost:3000` for Next.js).
- [x] **API Rate Limiting Middleware**:
  - Install token bucket rate limiting on `/auth` (20 req/min), `/upload` (5 req/min), and `/chat` (10 req/min).

---

## 📂 2. Storage & Database Hardening
- [x] **Workspace Database Seeding & Migration Integrity**:
  - Auto-generated database tables using `Base.metadata.create_all` during startup is supported, but in production, tables are fully managed via standard `alembic` migrations.
- [x] **Vector Store Sync Deletions**:
  - When deleting a document from PostgreSQL, cascade vector deletions by retrieving vector ids and executing reconstruction-based index cleanup in FAISS.
- [ ] **Persistent Shared Upload Volume**:
  - Currently, uploads are bind-mounted to `./backend/uploads`. For production container scaling, transition the uploads directory to a highly available shared file storage system (e.g. AWS EFS, Google Cloud Storage, or MinIO).

---

## 📈 3. Monitoring & Job Resilience
- [x] **Structured Logging & Trace Correlation**:
  - Ensure all request contexts inject a standard `X-Correlation-ID` header and bind it to structlog logger traces.
- [x] **Structured Exception Taxonomy**:
  - Ensure all ingestion parsing blocks categorize errors cleanly inside `Document.metadata_json` so the frontend can display troubleshooting tooltips instead of tracebacks.
- [ ] **Celery Worker Dead-Letter Queues**:
  - Wire up a Celery dead-letter queue (DLQ) to redirect permanently failed ingestion jobs for administrator review.
- [ ] **FAISS Index Sync Locks**:
  - Since FAISS runs in-memory and saves files to disk, concurrent ingestion jobs could potentially result in file-write race conditions.
  - For distributed production scaling, switch `VECTOR_STORE_TYPE` in `.env` to `pinecone` or integrate redis-based distributed locks (`redlock`) around FAISS write operations.

---

## 🗄️ 4. Alembic Migrations & Rollback Procedures

### Executing Migrations in Container
- **Run Migrations**:
  ```bash
  docker exec -t rag_api alembic upgrade head
  ```
- **Generate New Migration**:
  ```bash
  docker exec -t rag_api alembic revision --autogenerate -m "Migration details"
  ```

### Rollback (Downgrade) Instructions
- **Rollback 1 Version (Step-by-Step)**:
  ```bash
  docker exec -t rag_api alembic downgrade -1
  ```
- **Rollback to Specific Revision**:
  ```bash
  docker exec -t rag_api alembic downgrade <revision_id>
  ```
- **Reset Database Schema (Completely Downgrade to Base)**:
  ```bash
  docker exec -t rag_api alembic downgrade base
  ```

