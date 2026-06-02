# Nexus RAG Production Incident Response Notes

This operational manual outlines response procedures, debugging workflows, and recovery strategies for handling critical incidents, errors, or performance degradations in the Nexus RAG production platform.

---

## 🔍 1. Log Trace Audit & Correlation IDs

To facilitate rapid troubleshooting across multi-tenant API requests, Nexus RAG propagates a unique **Correlation ID** through all layers (Frontend ➔ Nginx ➔ FastAPI ➔ Celery Worker ➔ Postgres).

### How to Retrieve Logs by Correlation ID
Every HTTP response header contains `X-Correlation-ID` (e.g. `X-Correlation-ID: req-7b49f82d-8e43-4fb4-bf4b-91d154ee0d8d`). If a user reports a failed request or chat completion, retrieve that ID and run a centralized audit trace:

```bash
# Trace logs in the API service
docker compose -f docker-compose.prod.yml logs api | grep "req-7b49f82d-8e43-4fb4-bf4b-91d154ee0d8d"

# Trace background worker logs (such as ingestion, embeddings, indexing)
docker compose -f docker-compose.prod.yml logs worker | grep "req-7b49f82d-8e43-4fb4-bf4b-91d154ee0d8d"
```

Logs will output in structured JSON or unified formats matching:
`[2026-05-26 21:58:00] [INFO] [req-7b49f82d-8e43-4fb4-bf4b-91d154ee0d8d] User 12 uploaded document_id=45. Starting Celery parse task.`

---

## ⚡ 2. Database Connection Pool Exhaustion

### Signs of Connection Exhaustion:
- Client requests hang or return HTTP `504 Gateway Timeout`.
- Logs display: `sqlalchemy.exc.TimeoutError: QueuePool limit of size 10 overflow 10 reached, connection timed out`.
- Postgres container reports: `FATAL: remaining connection slots are reserved for non-replication superuser connections`.

### Immediate Mitigation & Recovery Steps:

1. **Audit Live Active Connections**:
   Log into Postgres and run the following command to count active connections grouped by application name and state:
   ```bash
   docker compose -f docker-compose.prod.yml exec db psql -U postgres -d rag_db -c "
   SELECT count(*), state, application_name 
   FROM pg_stat_activity 
   GROUP BY state, application_name;"
   ```

2. **Terminate Leaked/Hanging Sessions**:
   Forcefully terminate idle sessions that have been open for more than 10 minutes:
   ```bash
   docker compose -f docker-compose.prod.yml exec db psql -U postgres -d rag_db -c "
   SELECT pg_terminate_backend(pid) 
   FROM pg_stat_activity 
   WHERE state = 'idle' AND state_change < current_timestamp - interval '10 minutes';"
   ```

3. **Adjust Connection Configurations**:
   If legitimate traffic demands larger pools, modify the database pool size in `.env.production`:
   ```ini
   # Increase limits in .env.production
   DB_POOL_SIZE=20
   DB_MAX_OVERFLOW=10
   ```
   Then restart the API and worker containers:
   ```bash
   docker compose -f docker-compose.prod.yml up -d api worker
   ```

---

## 🗂️ 3. Corrupted Local FAISS Index Recovery

If the local FAISS index files on disk become corrupted, deleted, or out-of-sync with the Postgres database chunks, RAG searches will fail or return stale data.

### Signs of Index Corruption:
- Logs report: `RuntimeError: Error in read_index: cannot open file` or index size mismatch.
- A user deletes a document but search queries still retrieve its text snippets (deletion sync failed).
- RAG queries return no sources even though documents are marked as `indexed` in the UI.

### Step-by-Step Restoration Protocol:

Because the database holds the ultimate source of truth (full document metadata, chunk text, and document ownership), the FAISS index can be completely reconstructed from PostgreSQL records at any time.

1. **Locate the Workspace's Storage Path**:
   FAISS files are stored in `/app/storage/faiss_index` inside the worker container, segregated by workspace ID (e.g. `/app/storage/faiss_index/workspace_12/index.faiss`).

2. **Run the Administrative Re-Indexing CLI Task**:
   Execute the dedicated administrative script inside the running backend container to pull chunks for the affected workspace, regenerate the OpenAI embeddings, and reconstruct the index:
   ```bash
   # Re-index a single workspace
   docker compose -f docker-compose.prod.yml exec api python -m app.scripts.rebuild_index --workspace-id 12

   # Re-index all workspaces globally
   docker compose -f docker-compose.prod.yml exec api python -m app.scripts.rebuild_index --all
   ```

3. **Verify the Rebuilt File**:
   Ensure new physical index files are present and contain valid bytes:
   ```bash
   docker compose -f docker-compose.prod.yml exec worker ls -lh /app/storage/faiss_index/workspace_12/
   ```

---

## 🚫 4. OpenAI API Quota & Rate Limit Exhaustion

### Signs of Quota/Rate Exhaustion:
- Worker logs show `openai.RateLimitError: You exceeded your current quota, please check your plan and billing details`.
- UI displays "Index Failure" or "Chat Synthesis Failure".

### Action Plan:

1. **Verify API Quota Usage**:
   Log into the [OpenAI Platform Dashboard](https://platform.openai.com) and check billing, active API credits, and rate-limit tiers (TPM/RPM limits).

2. **Implement Rate Limiter Throttle Backoff**:
   Celery is configured to automatically retry embedding generation on rate limit triggers using exponential backoff. Confirm that Celery worker retry logic is active in logs:
   `[WARNING] RateLimitError encountered. Retrying in 16 seconds...`

3. **Swap API Keys Swiftly**:
   If the active key is revoked or exhausted, swap to a fallback secondary key in `.env.production` without bringing down the database:
   ```bash
   # Update .env.production
   sed -i 's/OPENAI_API_KEY=.*/OPENAI_API_KEY=sk-proj-NEW-FALLBACK-KEY/' .env.production
   
   # Gracefully reload API and Worker to pull new environment values
   docker compose -f docker-compose.prod.yml up -d --no-deps api worker
   ```

---

## 📁 5. Storage Cleansing & Volume Cleanup

Over time, deleted documents can leave orphan chunk directories, or failed uploads can consume local disk space.

### Cleanup Commands:

1. **Clean Orphan Physical Uploads**:
   Run the database sync-validator script to clean up any files in `/app/uploads` that no longer have metadata records in PostgreSQL:
   ```bash
   docker compose -f docker-compose.prod.yml exec api python -m app.scripts.cleanup_storage
   ```

2. **Purge Failed Ingestion Jobs from Redis Queue**:
   If Celery has blocked or dead-letter queues containing thousands of failed retry attempts, purge the broker clean:
   ```bash
   docker compose -f docker-compose.prod.yml exec redis redis-cli flushall
   # Restart the worker to clear cache memory
   docker compose -f docker-compose.prod.yml restart worker
   ```
