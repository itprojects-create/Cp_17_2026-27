import os


# Tests use the deterministic double explicitly; production defaults to a real
# provider and reports configuration failures instead of silently mocking.
os.environ.setdefault("MOCK_LLM_ENABLED", "true")

from app.config import settings
from app.agent import llm_loader

settings.MOCK_LLM_ENABLED = True
settings.LLM_PROVIDER = "mock"
settings.NVIDIA_API_KEY = ""
settings.GEMINI_API_KEY = ""
settings.GOOGLE_API_KEY = ""
settings.OPENAI_API_KEY = ""
settings.GROK_API_KEY = ""
settings.ANTHROPIC_API_KEY = ""
llm_loader.reset_llm()

import pytest


@pytest.fixture(scope="session", autouse=True)
def _initialized_database():
    # Mirrors app startup: a fresh checkout (or CI) has no SQLite schema since
    # *.db is gitignored, and some tests query tables before any app startup.
    from app.db.init_db import init_db

    init_db()


@pytest.fixture(scope="session", autouse=True)
def _ingested_knowledge_base():
    # Mirrors app startup: RAG tests need a populated vector store, and a fresh
    # checkout (or CI) has none since chroma_db/ is gitignored.
    from app.rag.vectorstore import get_vectorstore_count
    from app.rag.ingest import ingest_knowledge_base

    if get_vectorstore_count() == 0:
        ingest_knowledge_base()
