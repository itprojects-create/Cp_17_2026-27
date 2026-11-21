import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

KB_DIR = Path(__file__).resolve().parents[3] / "knowledge_base"


def _fallback_search(query: str, k: int, filter: Optional[dict] = None) -> dict:
    terms = [t for t in query.lower().split() if len(t) > 2]
    ranked = []

    for file in sorted(KB_DIR.glob("*.md")):
        if filter and "$or" in filter:
            allowed = [cond["source"]["$contains"] for cond in filter["$or"]]
            if not any(a in file.name for a in allowed):
                continue

        content = file.read_text(encoding="utf-8")
        hay = content.lower()
        score = sum(1 for t in terms if t in hay)
        if score > 0:
            ranked.append((score, file, content))

    ranked.sort(key=lambda row: row[0], reverse=True)
    top = ranked[:k]

    context_chunks = []
    sources = []
    citations = []
    for idx, (score, file, content) in enumerate(top):
        context_chunks.append(content[:900])
        sources.append(file.name)
        title = file.stem.replace("_", " ").title()
        citations.append({
            "source": file.name,
            "section": title,
            "title": title,
            "reference": f"{file.name} > {title}",
            "context_id": f"{file.name}::{title}::{idx}",
            "score": float(score),
            "similarity": 0.8,
        })

    return {
        "context": "\n\n".join(context_chunks),
        "citations": citations,
        "sources": sources,
    }


@tool
def search_kb(
    query: str,
    k: int = 3,
    filter: Optional[dict] = None,
    persona: Optional[dict] = None,
) -> dict:
    """Search the knowledge base and return context plus formatted source references."""
    try:
        from app.rag.retriever import retrieve_context

        result = retrieve_context(query, k=k, filter=filter, persona=persona)
        context = result.get("context", "")
        citations = result.get("citations", [])
        sources = result.get("sources", [])

        return {
            "context": context,
            "citations": citations,
            "sources": sources,
        }
    except Exception as e:
        logger.error("search_kb error: %s", e)
        fallback = _fallback_search(query, k, filter=filter)
        fallback["error"] = str(e)
        return fallback
