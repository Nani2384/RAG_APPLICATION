# Enterprise Multimodal RAG Application

A massive, highly-scalable, resilient, and intelligent Retrieval-Augmented Generation (RAG) platform.
It uses **FastAPI**, **Celery**, **PostgreSQL**, **Redis**, **Pinecone/FAISS**, and **Next.js**.

## Core Features
- **Extensive Background Ingestion:** Async reliable queue processing using Celery & Redis.
- **Multimodal Data Support:** `unstructured` based processing strategy (PDFs, PPTXs, HTML).
- **Pluggable Architecture:** Easy to swap FAISS vector store with Pinecone or Qdrant for production scale.
- **Strict Adherence Intelligence:** Generator explicitly prevents hallucinations using answer-only-from-context prompt chaining.
- **Premium Frontend:** Next.js with deep TailwindCSS aesthetics, dark-mode, and Server-Sent Event (SSE) chat streaming.
- **Robustness at Scale:** Dockerized, structlog integration, environment-based configurations using Pydantic Settings.

## Getting Started

1. Make sure you have Docker installed.
2. Run the automated setup. You must add your `OPENAI_API_KEY` to the `.env` file before proceeding.
```bash
./setup.sh
```
3. Boot the environment
```bash
docker compose up
```

## Structure
- `/backend`: The core intelligence, API, and queuing backend.
- `/frontend`: The interactive UI for document chatting and user controls.
# Rag-Application
