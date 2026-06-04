from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "rag_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1
)

import asyncio
import json
import nltk

# Auto-download required NLTK packages for unstructured document parsing
for resource in ["punkt", "punkt_tab", "averaged_perceptron_tagger", "averaged_perceptron_tagger_eng"]:
    try:
        nltk.download(resource, quiet=True)
    except Exception:
        pass

async def async_get_document_workspace_id(document_id: int) -> int:
    from app.core.database import AsyncSessionLocal
    from app.models.domain import Document
    from sqlalchemy.future import select
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Document).where(Document.id == document_id))
        doc = result.scalars().first()
        if not doc:
            raise ValueError(f"Document {document_id} not found in database.")
        return doc.workspace_id

async def async_update_document_status(
    document_id: int, 
    status: str, 
    vector_ids: list = None, 
    error_msg: str = None,
    error_meta: dict = None,
    retry_meta: dict = None
):
    from app.core.database import AsyncSessionLocal
    from app.models.domain import Document
    from sqlalchemy.future import select
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Document).where(Document.id == document_id))
        doc = result.scalars().first()
        if not doc:
            return
        
        doc.status = status
        if vector_ids is not None:
            doc.vector_ids = json.dumps(vector_ids)
            
        meta = json.loads(doc.metadata_json) if doc.metadata_json else {}
        
        if error_msg is not None:
            meta["error"] = error_msg
        if error_meta is not None:
            meta.update(error_meta)
        if retry_meta is not None:
            meta.update(retry_meta)
            
        doc.metadata_json = json.dumps(meta)
        await session.commit()

def categorize_error(e: Exception) -> dict:
    error_str = str(e)
    if isinstance(e, FileNotFoundError):
        return {
            "error_type": "File Access Failure",
            "error_details": "The ingestion worker was unable to locate or read the uploaded file from disk storage.",
            "troubleshooting": "Please verify if the file was deleted or if there are permission constraints on the shared storage volume."
        }
    elif "quota" in error_str.lower() or "429" in error_str or "insufficient_quota" in error_str:
        return {
            "error_type": "Model Provider Quota Limit",
            "error_details": "The OpenAI API key quota limit has been exceeded or the account has insufficient credits.",
            "troubleshooting": "Please check your OpenAI billing plan, or wait for the system to process chunks using local offline fallbacks."
        }
    elif "pdfminer" in error_str.lower() or "partition" in error_str.lower() or "unstructured" in error_str.lower() or "import" in error_str.lower():
        return {
            "error_type": "Document Parsing Failure",
            "error_details": "The system encountered an error extracting text content using the unstructured parsing library.",
            "troubleshooting": "Verify that the document format is not corrupted and is text-extractable. Supported types: PDF, PPTX, DOCX, TXT."
        }
    elif "faiss" in error_str.lower() or "index" in error_str.lower() or "vector" in error_str.lower():
        return {
            "error_type": "Vector Store Failure",
            "error_details": "The system was unable to write or query vector index representations in FAISS.",
            "troubleshooting": "Check file write permissions for the `/app/storage` folder inside the backend containers."
        }
    else:
        return {
            "error_type": "General Ingestion Failure",
            "error_details": f"An unexpected system exception occurred during document indexing: {error_str}",
            "troubleshooting": "Please check the Celery worker container logs for trace details or try re-uploading."
        }

async def async_run_ingestion_pipeline_with_retry(self, document_id: int, file_path: str):
    import structlog
    logger = structlog.get_logger(__name__)
    
    try:
        from app.services.ingestion import IngestionService
        from app.core.database import engine, AsyncSessionLocal
        
        # 1. Update status to processing and fetch workspace_id
        await async_update_document_status(document_id, "processing")
        workspace_id = await async_get_document_workspace_id(document_id)
        
        # 2. Process document indexing
        service = IngestionService()
        vector_ids = service.process_document(file_path, document_id, workspace_id)
        
        # 3. Update status to indexed on success
        async with AsyncSessionLocal() as session:
            from app.models.domain import Document
            from sqlalchemy.future import select
            result = await session.execute(select(Document).where(Document.id == document_id))
            doc = result.scalars().first()
            if doc:
                doc.status = "indexed"
                doc.vector_ids = json.dumps(vector_ids)
                doc.metadata_json = json.dumps({}) # clear metadata
                await session.commit()
                
        return {"status": "success", "vector_ids": vector_ids}
    except Exception as e:
        retries = self.request.retries
        max_retries = self.max_retries
        
        if retries < max_retries:
            countdown = 5 * (2 ** retries) # Exponential backoff: 5s, 10s, 20s
            logger.warn(f"Ingestion failed for document {document_id}. Scheduling retry {retries + 1}/{max_retries} in {countdown}s...", error=str(e))
            
            retry_meta = {
                "current_retry": retries + 1,
                "max_retries": max_retries,
                "retry_countdown": countdown,
                "error": str(e)
            }
            # Record retry attempt in database within the SAME async event loop
            await async_update_document_status(document_id, "processing", retry_meta=retry_meta)
            return {"status": "retry", "countdown": countdown, "exception": e}
        else:
            logger.error(f"Ingestion failed for document {document_id} after {max_retries} retries. Marking as error.", error=str(e))
            err_meta = categorize_error(e)
            # Record final error within the SAME async event loop
            await async_update_document_status(document_id, "error", error_msg=str(e), error_meta=err_meta)
            return {"status": "error", "exception": e, "category": err_meta["error_type"]}
    finally:
        try:
            await engine.dispose()
        except Exception as err_disp:
            logger.error("Failed to dispose database engine", error=str(err_disp))

@celery_app.task(bind=True, name="process_document_job", max_retries=3)
def process_document_job(self, document_id: int, file_path: str):
    import structlog
    import asyncio
    
    logger = structlog.get_logger(__name__)
    logger.info(f"Received job for {document_id} at {file_path}. Retry count: {self.request.retries}")
    
    res = asyncio.run(async_run_ingestion_pipeline_with_retry(self, document_id, file_path))
    
    if res["status"] == "success":
        return {"status": "success", "document_id": document_id, "vectors_inserted": len(res["vector_ids"])}
    elif res["status"] == "retry":
        raise self.retry(exc=res["exception"], countdown=res["countdown"])
    else:
        return {"status": "error", "error": str(res["exception"]), "category": res.get("category")}
