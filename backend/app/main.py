import logging
import sys
import time
import uuid
from collections import defaultdict
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
import structlog
from app.core.config import settings

# 1. High-Fidelity Structured Logging Configuration with Correlation Context
def configure_logging():
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.dev.ConsoleRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        cache_logger_on_first_use=True,
    )

configure_logging()
logger = structlog.get_logger(__name__)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Enterprise Multi-Modal RAG Platform",
)

# 2. Correlation ID Middleware for Traceability
class CorrelationIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(correlation_id=correlation_id)
        
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        return response

app.add_middleware(CorrelationIDMiddleware)

# 3. Custom API Rate Limiting Middleware
class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.buckets = defaultdict(lambda: defaultdict(list))
        self.config = {
            "/api/v1/auth": (20, 60),
            "/api/v1/documents/upload": (5, 60),
            "/api/v1/chat/completions": (10, 60)
        }

    async def dispatch(self, request: Request, call_next):
        import os
        if os.environ.get("TESTING") == "true":
            return await call_next(request)
            
        client_ip = request.client.host if request.client else "unknown"
        path = request.url.path
        
        limit_rule = None
        for route_prefix, rule in self.config.items():
            if path.startswith(route_prefix):
                limit_rule = (route_prefix, rule[0], rule[1])
                break
                
        if limit_rule:
            prefix, limit, window = limit_rule
            now = time.time()
            
            # Clean up old timestamps outside window
            self.buckets[client_ip][prefix] = [
                ts for ts in self.buckets[client_ip][prefix]
                if now - ts < window
            ]
            
            if len(self.buckets[client_ip][prefix]) >= limit:
                logger.warn(
                    "API rate limit exceeded",
                    client_ip=client_ip,
                    path=path,
                    limit=limit,
                    window=window
                )
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "detail": "Too many requests. Please slow down and try again later.",
                        "retry_after": int(window - (now - self.buckets[client_ip][prefix][0]))
                    }
                )
                
            self.buckets[client_ip][prefix].append(now)
            
        return await call_next(request)

app.add_middleware(RateLimitMiddleware)

# 4. Whitelisted Secure CORS Middleware
origins = [origin.strip() for origin in settings.ALLOWED_CORS_ORIGINS.split(",")] if settings.ALLOWED_CORS_ORIGINS else ["http://localhost:3000"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    import os
    if os.environ.get("TESTING") == "true":
        logger.info("Skipping database initialization and seeding in testing mode.")
        return
        
    logger.info("Starting up FastAPI service.")
    logger.info("Initializing database tables...")
    try:
        from app.core.database import engine, AsyncSessionLocal
        from app.models.domain import Base, User, Workspace
        from sqlalchemy.future import select

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables initialized successfully.")

        # Seed default user and workspace with secure password hash
        logger.info("Checking and seeding default database entities...")
        async with AsyncSessionLocal() as session:
            # 1. Seed user with ID 1
            user_result = await session.execute(select(User).where(User.id == 1))
            user = user_result.scalar_one_or_none()
            if not user:
                # Also check by email to be safe
                email_result = await session.execute(select(User).where(User.email == "admin@ragplatform.com"))
                user = email_result.scalar_one_or_none()
                if not user:
                    from app.core.security import get_password_hash
                    hashed_pwd = get_password_hash("admin123")
                    user = User(id=1, email="admin@ragplatform.com", hashed_password=hashed_pwd)
                    session.add(user)
                    await session.commit()
                    await session.refresh(user)
                    logger.info("Seeded default user (ID 1, admin@ragplatform.com, password hashed).")

            # 2. Seed workspace with ID 1
            workspace_result = await session.execute(select(Workspace).where(Workspace.id == 1))
            workspace = workspace_result.scalar_one_or_none()
            if not workspace:
                workspace = Workspace(id=1, name="Default Workspace", owner_id=user.id)
                session.add(workspace)
                await session.commit()
                logger.info("Seeded default workspace (ID 1).")

        logger.info("Database seeding checked and completed.")
    except Exception as e:
        logger.error("Failed to initialize or seed database.", error=str(e))

@app.get("/health")
async def health_check():
    return {"status": "ok", "version": settings.VERSION}

# Import routers here
from app.api.v1.api import api_router
app.include_router(api_router, prefix="/api/v1")
