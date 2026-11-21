"""
Persona-aware RAG retriever module.

Primary mechanism: Semantic similarity search across ChromaDB vector store.
Relevance enhancement: Soft persona re-ranking based on role, seniority, and technology stack.
Safety: Ensures generic company documentation (policies, company overview, FAQ, org structure)
remains highly accessible for all personas without hard-filtering.
"""
import logging
from typing import List, Dict, Optional, Any
from app.rag.vectorstore import get_vectorstore
from app.config import settings

logger = logging.getLogger(__name__)


def _distance_to_similarity(distance: float, metric: str) -> float:
    """Convert the distance returned by Chroma using the collection's metric."""
    if metric == "cosine":
        similarity = 1.0 - (distance / 2.0)
    elif metric == "l2":
        similarity = 1.0 / (1.0 + max(distance, 0.0))
    elif metric == "ip":
        similarity = 1.0 - distance
    else:
        raise ValueError(f"Unsupported Chroma distance metric: {metric}")
    return max(0.0, min(1.0, similarity))


def _get_distance_metric(vectorstore: Any) -> str:
    collection = getattr(vectorstore, "_collection", None)
    configuration = getattr(collection, "configuration", None) if collection else None
    metric = configuration.get("hnsw", {}).get("space") if isinstance(configuration, dict) else None
    if metric is None:
        metadata = getattr(collection, "metadata", None) if collection else None
        metric = metadata.get("hnsw:space") if isinstance(metadata, dict) else None
    if not metric:
        raise ValueError("Chroma collection does not expose a distance metric")
    return str(metric).lower()


def _compute_persona_boost(metadata: Dict[str, Any], persona: Optional[Dict[str, Any]]) -> float:
    """
    Calculate soft relevance boost based on persona metadata match.
    Gives a positive bump to role/stack-aligned chunks while keeping generic chunks competitive.
    """
    if not persona:
        return 0.0

    boost = 0.0
    user_role = str(persona.get("role") or "").lower().strip()
    user_level = str(persona.get("experience_level") or persona.get("level") or "").lower().strip()
    user_stack = persona.get("technology_stack") or persona.get("stack") or []
    if isinstance(user_stack, str):
        user_stack = [s.strip().lower() for s in user_stack.split(",") if s.strip()]
    else:
        user_stack = [str(s).strip().lower() for s in user_stack if str(s).strip()]

    chunk_role = str(metadata.get("role", "all")).lower().strip()
    chunk_tech = str(metadata.get("technology", "General")).lower().strip()
    chunk_level = str(metadata.get("experience_level", "all")).lower().strip()

    # Role alignment boost
    if user_role and chunk_role != "all":
        if chunk_role == user_role:
            boost += 0.15
        else:
            # Subtle penalty for explicitly mismatched roles on role-specific docs
            boost -= 0.05

    # Technology stack alignment boost
    if user_stack and chunk_tech != "general":
        if any(tech in chunk_tech or chunk_tech in tech for tech in user_stack):
            boost += 0.15

    # Seniority alignment boost (e.g. senior practices / SLAs vs intern guides)
    if user_level and chunk_level != "all":
        if chunk_level == user_level:
            boost += 0.05

    return boost


def retrieve_context(
    query: str,
    k: int = 4,
    filter: Optional[Dict[str, Any]] = None,
    persona: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Retrieve relevant knowledge base chunks using semantic similarity as the primary mechanism,
    with persona-aware soft re-ranking when persona metadata is provided.
    """
    vectorstore = get_vectorstore()
    threshold = settings.RAG_SCORE_THRESHOLD
    metric = _get_distance_metric(vectorstore)
    if metric == "l2":
        threshold = max(threshold, 0.405)

    # Fetch diverse candidates for re-ranking
    fetch_k = max(k * 6, 25)

    try:
        if filter:
            results = vectorstore.similarity_search_with_score(query, k=fetch_k, filter=filter)
        else:
            results = vectorstore.similarity_search_with_score(query, k=fetch_k)
    except Exception as exc:
        logger.error("Vectorstore similarity search failed: %s", exc)
        return {"context": "", "citations": [], "sources": []}

    scored_candidates = []

    for doc, distance in results:
        similarity = _distance_to_similarity(float(distance), metric)

        if similarity < threshold:
            logger.debug(
                "Skipping chunk from %s (section: %s) due to similarity %.4f < threshold %.4f",
                doc.metadata.get("source"),
                doc.metadata.get("section"),
                similarity,
                threshold,
            )
            continue

        boost = _compute_persona_boost(doc.metadata, persona)
        final_score = similarity + boost

        scored_candidates.append({
            "doc": doc,
            "raw_score": float(distance),
            "similarity": similarity,
            "boost": boost,
            "final_score": final_score,
            "metadata": doc.metadata,
        })

    # Sort candidates by final persona-augmented score descending
    scored_candidates.sort(key=lambda item: item["final_score"], reverse=True)
    top_candidates = scored_candidates[:k]

    context_chunks = []
    citations = []
    sources = []

    for item in top_candidates:
        doc = item["doc"]
        meta = item["metadata"]
        source_name = meta.get("source", "knowledge_base")
        section_title = meta.get("section") or meta.get("title") or ""

        header_prefix = f"### [{source_name}] {section_title}".strip() if section_title else f"### [{source_name}]"
        context_chunks.append(f"{header_prefix}\n{doc.page_content}")

        doc_title = meta.get("title") or section_title or source_name
        ref = f"{source_name} > {section_title}" if section_title else source_name
        ctx_id = f"{source_name}::{section_title}::{len(citations)}"

        citations.append({
            "source": source_name,
            "section": section_title,
            "title": doc_title,
            "reference": ref,
            "context_id": ctx_id,
            "score": item["raw_score"],
            "similarity": item["similarity"],
            "final_score": item["final_score"],
            "role": meta.get("role", "all"),
            "technology": meta.get("technology", "General"),
            "category": meta.get("category", "Documentation"),
        })

        if source_name not in sources:
            sources.append(source_name)

    return {
        "context": "\n\n".join(context_chunks),
        "citations": citations,
        "sources": sources,
    }