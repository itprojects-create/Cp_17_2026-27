import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from app.routes.sessions import router as session_router
from app.routes.auth import router as auth_router
from app.routes.knowledge import router as knowledge_router
from app.routes.settings import router as settings_router, system_router
from app.routes.profile import router as profile_router
from app.routes.dashboard import router as dashboard_router
from app.routes.github import router as github_router
from app.db.init_db import init_db
from app.db.database import SessionLocal
from app.db.demo_seed import seed_demo_dashboard_data
from app.rag.vectorstore import get_vectorstore, get_vectorstore_count
from app.rag.ingest import ingest_knowledge_base
from app.agent.llm_loader import get_llm_provider_info, get_llm
from app.config import settings
from app.log_redaction import install_log_redaction

logger = logging.getLogger(__name__)
install_log_redaction()

# Rate limiter — uses client IP address as the key
limiter = Limiter(key_func=get_remote_address)


import uuid
import time
from fastapi import Request

@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan: startup → yield → shutdown."""
    # --- Startup ---
    # Centralized configuration & security validation
    settings.validate_configuration()

    # Startup order is intentional: schema → demo seed → optional KB ingestion → LLM check.
    init_db()

    if settings.DEBUG:
        try:
            def _seed_demo_data() -> bool:
                db = SessionLocal()
                try:
                    return seed_demo_dashboard_data(db)
                finally:
                    db.close()

            await asyncio.to_thread(_seed_demo_data)
        except Exception as exc:
            logger.error("Demo dashboard seeding failed: %s", exc)

    # Background initialization: Ingest knowledge base and verify LLM without blocking server startup
    async def _async_background_init():
        try:
            if get_vectorstore_count() == 0:
                logger.info("Vectorstore empty - running background ingestion...")
                await asyncio.to_thread(ingest_knowledge_base)
                logger.info("Vectorstore background ingestion completed.")
            # Load the embedding model now so the first user query doesn't pay for it.
            await asyncio.to_thread(get_vectorstore)
        except Exception as exc:
            logger.warning("KB ingestion failed: %s - RAG will use fallback retrieval", exc)

        try:
            llm_info = get_llm_provider_info()
            logger.info("🤖 LLM Provider Active: %s", llm_info)
            if settings.DEBUG and llm_info.get("status") == "active":
                try:
                    from langchain_core.messages import HumanMessage
                    llm = get_llm()
                    response = await asyncio.to_thread(
                        lambda: llm.invoke([HumanMessage(content="Ping")])
                    )
                    logger.info("✅ LLM self-test passed: response preview='%s'", str(response.content)[:30])
                except Exception as test_exc:
                    logger.warning("LLM startup self-test note: %s", test_exc)
        except Exception as llm_exc:
            logger.warning("Failed to check LLM provider info: %s", llm_exc)

    asyncio.create_task(_async_background_init())

    # Debug: Log all registered routes
    if settings.DEBUG:
        for route in app.routes:
            logger.debug(" - %s", getattr(route, 'path', str(route)))

    yield
    # --- Shutdown (add cleanup here if needed) ---


app = FastAPI(lifespan=lifespan)

# Request ID, latency tracing, and COOP header middleware
@app.middleware("http")
async def add_process_time_and_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    start_time = time.perf_counter()
    response = await call_next(request)
    process_time = (time.perf_counter() - start_time) * 1000
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Response-Time-Ms"] = f"{process_time:.2f}"
    # Allow Google OAuth popups to communicate back to the opener window.
    # Without this, COOP blocks window.closed / postMessage across origins.
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin-allow-popups"
    return response

# Attach rate limiter state & handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(auth_router, prefix="/api")
app.include_router(session_router, prefix="/api")
app.include_router(knowledge_router, prefix="/api")
app.include_router(settings_router, prefix="/api")
app.include_router(system_router, prefix="/api")
app.include_router(profile_router, prefix="/api")
app.include_router(dashboard_router, prefix="/api")
app.include_router(github_router, prefix="/api")


@app.get("/")
def root():
    return {"message": "Autonomous Developer Onboarding Agent API"}


@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


@app.get("/favicon.ico")
def favicon():
    return {}