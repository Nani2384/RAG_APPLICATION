# Nexus RAG Automated Testing Guide

This guide describes the automated testing architecture, execution commands, mock strategies, and coverage scopes for the Nexus RAG platform.

---

## 🏗️ 1. Testing Architecture Overview

Nexus RAG uses a dual-layer testing strategy to ensure backend logic correctness and frontend user-flow integrity:

```
                  ┌──────────────────────────────────────────┐
                  │          Playwright E2E Tests            │
                  │   • chromium, firefox, webkit engines    │
                  │   • Auth modal, chat streams, uploads    │
                  └────────────────────┬─────────────────────┘
                                       │ (Simulates User Actions)
                                       ▼
                  ┌──────────────────────────────────────────┐
                  │       pytest-asyncio Integration         │
                  │   • High-speed local SQLite isolation    │
                  │   • Deterministic synchronous Celery     │
                  └──────────────────────────────────────────┘
```

1. **Backend Integration Suite (`pytest` + `pytest-asyncio`)**:
   - Runs against an isolated, high-speed SQLite file database (`/tmp/test.db`), avoiding all PostgreSQL connection locks and transaction pollution.
   - Forces Celery tasks to process synchronously in the same thread using eager execution context (`task_always_eager = True`).
   - Automatically mocks OpenAI API embedding calls to prevent network flakiness and credit depletion.
2. **Frontend End-to-End Suite (`Playwright`)**:
   - Spawns actual browser engines (Chromium, Firefox, WebKit) to verify click-flows, form states, and graceful error alerts on HTTP `401 Unauthorized` responses.

---

## 🧪 2. Running Backend Integration Tests

### Execution Command
Execute the full pytest suite inside the running backend API container:
```bash
docker exec -t rag_api pytest -v tests/
```

### Coverage Analysis
To run tests with code coverage metrics:
```bash
docker exec -t rag_api pytest --cov=app -v tests/
```

### Scope of Test Cases
- **`test_auth.py`**:
  - `test_register_success`: Verifies new account creation and default workspace seeding.
  - `test_register_duplicate_email`: Confirms registration blocks duplicate emails.
  - `test_register_password_too_short`: Blocks passwords under 8 characters.
  - `test_login_success`: Validates bcrypt hashed passwords and signed JWT output.
  - `test_get_current_user_secure`: Verifies JWT dependency signature validation.
  - `test_get_current_user_bypass`: Validates developer mock token authentication.
- **`test_workspace_isolation.py`**:
  - `test_workspace_isolation_completions`: Proves User B cannot access User A's workspace, returning `403 Forbidden`.
  - `test_workspace_isolation_documents`: Confirms document queries strictly separate files by owner ID.
- **`test_documents.py`**:
  - `test_upload_document_success`: Tests upload endpoint and Celery execution routing.
  - `test_list_documents`: Validates listing feeds.
  - `test_retry_document_ingestion_success`: Tests re-queueing of failed indexing jobs.
  - `test_ingestion_service_parsing`: Runs direct `IngestionService` document parsing checks.
- **`test_vector_deletions.py`**:
  - `test_cascading_document_deletion_success`: Verifies document deletes sweep Postgres, remove physical upload files from `/app/uploads`, and trigger flat index reconstructions in FAISS.

---

## 🎨 3. Running Frontend E2E Tests (Playwright)

### Prerequisite Installation
Install Playwright dependencies inside the frontend workspace:
```bash
cd frontend
npm install --save-dev @playwright/test
npx playwright install
```

### Running Tests
Execute the tests in headless mode (default):
```bash
npx playwright test
```

To run with UI debug mode (great for visual inspection):
```bash
npx playwright test --ui
```

### Playwright Test Scopes (`frontend/e2e/`):
1. **`auth.spec.ts`**: Verifies the glassmorphic Auth Portal appears on load, checks toggle actions, and tests the "Developer Bypass" flow.
2. **`chat.spec.ts`**: Simulates sending a query, verifies pulse/shimmer skeletons appear, and confirms standard conversational rendering.
3. **`upload.spec.ts`**: Navigates to "Ingestion Jobs" and verifies drop-zone components and empty table states.

---

## ⚙️ 4. Key Testing Mocks & Hacks

### 1. Mocking OpenAI Embeddings (`conftest.py`)
To prevent hitting API quotas, embedding methods are patched to return fixed-dimension arrays:
```python
@pytest.fixture(autouse=True)
def mock_embeddings():
    with patch("app.rag.embeddings.openai_embedder.OpenAIEmbedder.embed_documents") as mock_embeds, \
         patch("app.rag.embeddings.openai_embedder.OpenAIEmbedder.embed_query") as mock_query:
         mock_embeds.return_value = [[0.1] * 1536]
         mock_query.return_value = [0.1] * 1536
         yield
```

### 2. Rate Limit Testing Bypass (`main.py`)
To prevent test threads from hitting `429 Too Many Requests` limits during continuous execution, the rate-limiting middleware automatically bypasses when `TESTING` is active:
```python
if os.environ.get("TESTING") == "true":
    return await call_next(request)
```
