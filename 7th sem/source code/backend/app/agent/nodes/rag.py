from typing import Dict, Any
from langchain_core.messages import HumanMessage
from app.agent.tools.knowledge_tools import search_kb


def _last_human_message(state: dict) -> str:
    for message in reversed(state.get("messages", [])):
        if isinstance(message, HumanMessage):
            return message.content.strip()
    return ""


def run(state: dict) -> dict:
    query = _last_human_message(state)
    if not query:
        return {
            "retrieved_chunks": [],
            "retrieved_sources": [],
            "sources": [],
            "retrieved_documents": [],
            "structured_sources": [],
            "context_docs": "",
        }

    persona_info: Dict[str, Any] = {}
    if state.get("persona"):
        persona_info = dict(state.get("persona", {}))
    if state.get("role"):
        persona_info["role"] = state.get("role")
    if state.get("experience_level"):
        persona_info["experience_level"] = state.get("experience_level")
    if state.get("technology_stack"):
        persona_info["technology_stack"] = state.get("technology_stack")

    invoke_args: Dict[str, Any] = {
        "query": query,
        "k": 4,
        "persona": persona_info if persona_info else None,
    }

    result = search_kb.invoke(invoke_args)
    context = result.get("context", "")
    citations = result.get("citations", [])

    if not context.strip() or not citations:
        return {
            "retrieved_chunks": [],
            "retrieved_sources": [],
            "sources": [],
            "retrieved_documents": [],
            "structured_sources": [],
            "context_docs": "",
        }

    unique_sources = []
    for c in citations:
        src = c.get("source")
        if src and src not in unique_sources:
            unique_sources.append(src)

    chunks = [chunk for chunk in context.split("\n") if chunk.strip()]
    source_lines = [f"- {source}" for source in unique_sources]

    context_docs = context
    if source_lines:
        context_docs = f"{context}\n\nSources:\n" + "\n".join(source_lines)

    return {
        "retrieved_chunks": chunks,
        "retrieved_sources": unique_sources,
        "sources": unique_sources,
        "retrieved_documents": citations,
        "structured_sources": citations,
        "context_docs": context_docs,
    }
