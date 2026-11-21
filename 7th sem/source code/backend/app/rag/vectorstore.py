try:
    from langchain_huggingface import HuggingFaceEmbeddings
except Exception:  # pragma: no cover - fallback for older environments
    from langchain_community.embeddings import HuggingFaceEmbeddings

try:
    from langchain_chroma import Chroma
except Exception:  # pragma: no cover - fallback for older environments
    from langchain_community.vectorstores import Chroma

from functools import lru_cache

from app.config import settings

CHROMA_PATH = str(settings.CHROMA_DB_DIR)
COLLECTION_NAME = "novabyte_knowledge_base"


@lru_cache(maxsize=1)
def get_vectorstore():
    # Cached: building the embedding model takes several seconds, and doing it per
    # query made every retrieval slow enough to hit the Knowledge Base ask timeout.
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )

    vectorstore = Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=CHROMA_PATH
    )

    return vectorstore


def get_vectorstore_count() -> int:
    """Return the number of stored embeddings without requiring embedding model import."""
    vectorstore = Chroma(
        collection_name=COLLECTION_NAME,
        persist_directory=CHROMA_PATH,
    )

    if hasattr(vectorstore, "count"):
        return int(vectorstore.count())

    collection = getattr(vectorstore, "_collection", None)
    if collection is not None and hasattr(collection, "count"):
        return int(collection.count())

    return 0