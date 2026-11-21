import re
from langchain_core.messages import SystemMessage, AIMessage
from app.agent.llm_loader import get_llm
from app.services.persona_matcher import FALLBACK_PERSONA


SYSTEM_PROMPT = """You are NovaByte AI, an onboarding assistant.
Provide concise, grounded, action-oriented responses.

CRITICAL GROUNDING AND CITATION RULES:
1. Only answer using the retrieved Context below. Do NOT invent, assume, or hallucinate facts or citations.
2. If the retrieved Context does not contain sufficient information to answer the user's question, you MUST clearly state: "The knowledge base does not provide enough information to answer this question." and suggest contacting the team lead, HR, or IT.
3. NEVER fabricate source names, document titles, or citations not present in the verified Context.
"""


MODEL_SOURCES_LINE = re.compile(r"^[ \t]*[*_]*sources?[*_]*\s*:.*$\n?", re.IGNORECASE | re.MULTILINE)


# Replies the app itself saves when generation fails. They are notices, not things the
# assistant said: sent back as history, a model learns to repeat them verbatim.
ERROR_NOTICE_PREFIXES = (
    "the configured language-model provider is unavailable",
    "i encountered an issue processing your request",
    "i encountered an error while processing your request",
    "an error occurred while generating the response",
)


def is_error_notice_text(text) -> bool:
    """True for the app's own failure notices (stored with role "notice", not "assistant")."""
    return str(text or "").strip().lower().startswith(ERROR_NOTICE_PREFIXES)


def _is_error_notice(message) -> bool:
    # Also covers notices saved as assistant messages before the "notice" role existed.
    return getattr(message, "type", "") == "ai" and is_error_notice_text(message.content)


def _extract_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and "text" in item:
                parts.append(str(item["text"]))
        return "\n".join(parts)
    return str(content)


def run(state: dict) -> dict:
    llm = get_llm()
    context_docs = (state.get("context_docs") or "").strip()
    tool_results = state.get("tool_results", [])
    suggested_actions = state.get("suggested_actions", [])
    raw_citations = state.get("structured_sources") or state.get("retrieved_documents") or []
    intent = state.get("intent", "other")
    persona = state.get("persona") or {}

    # Checklist tasks the user's message refers to by ID (e.g. "the repo URL for BI-02").
    last_user_text = next(
        (str(m.content) for m in reversed(state.get("messages", [])) if getattr(m, "type", "") == "human"), ""
    ).upper()
    mentioned_tasks = [
        t for t in (state.get("checklist") or [])
        if t.get("task_id") and re.search(rf"\b{re.escape(str(t['task_id']).upper())}\b", last_user_text)
    ]

    # Verified citations to prevent any hallucinated/fabricated citations
    verified_sources: list[dict] = []
    for doc in raw_citations:
        if isinstance(doc, dict) and doc.get("source"):
            source_name = str(doc.get("source")).strip()
            section_title = str(doc.get("section") or doc.get("title") or "").strip()
            doc_title = str(doc.get("title") or section_title or source_name).strip()
            ref = str(doc.get("reference") or (f"{source_name} > {section_title}" if section_title else source_name)).strip()
            ctx_id = str(doc.get("context_id") or f"{source_name}::{section_title}::{len(verified_sources)}").strip()

            verified_sources.append({
                "source": source_name,
                "section": section_title or None,
                "title": doc_title or None,
                "reference": ref or None,
                "context_id": ctx_id or None,
                "category": doc.get("category"),
                "similarity": doc.get("similarity"),
                "score": doc.get("score"),
            })

    unique_source_names = []
    for item in verified_sources:
        s = item["source"]
        if s not in unique_source_names:
            unique_source_names.append(s)

    # 1. Clear insufficient context handling for question intent
    # (a question about the user's own task can still be answered from the checklist).
    if intent == "question" and (not context_docs or not verified_sources) and not mentioned_tasks:
        insufficient_msg = (
            "The knowledge base does not provide enough information to answer this question. "
            "Please reach out to your team lead, HR, or IT for further assistance."
        )
        ai_msg = AIMessage(content=insufficient_msg)
        return {
            "messages": [ai_msg],
            "response": insufficient_msg,
            "sources": [],
            "retrieved_sources": [],
            "retrieved_documents": [],
            "structured_sources": [],
        }

    context_block = ""
    if context_docs:
        context_block += f"\n\nContext:\n{context_docs}"
    if mentioned_tasks and not tool_results:
        context_block += "\n\nUser's onboarding tasks referenced in the question:\n" + "\n".join(
            f"- {t['task_id']} ({t.get('status', 'Pending')}): {t.get('title', '')} - {t.get('description', '')}"
            for t in mentioned_tasks
        )
    if tool_results:
        context_block += "\n\nTool Results:\n" + "\n".join(tool_results)
    if suggested_actions:
        context_block += "\n\nSuggested next actions:\n" + "\n".join(f"- {a}" for a in suggested_actions)

    persona_block = ""
    if persona:
        persona_block = (
            f"\nPersona: role={persona.get('role')}, level={persona.get('level')}, "
            f"stack={persona.get('stack')}"
        )

    system = SystemMessage(content=SYSTEM_PROMPT + f"\nIntent: {intent}{persona_block}{context_block}")
    MAX_HISTORY = 20
    conversation = [
        m for m in state.get("messages", [])
        if getattr(m, "type", "") != "system" and not _is_error_notice(m)
    ]
    conversation = conversation[-MAX_HISTORY:]

    try:
        ai_msg = llm.invoke([system] + conversation)
        content = _extract_text(ai_msg.content)
        # Models often add their own "Sources:" line; drop it so only the verified list is shown.
        content = MODEL_SOURCES_LINE.sub("", content).rstrip()
        if unique_source_names and "does not provide enough information" not in content.lower():
            content += f"\n\n*Sources: {', '.join(unique_source_names)}*"
        ai_msg = AIMessage(content=content)
    except Exception as e:
        import logging
        from app.config import settings
        provider_name = type(llm).__name__
        logging.getLogger(__name__).error(
            "LLM generation failed for provider '%s' (%s): %s",
            provider_name,
            type(e).__name__,
            e,
        )
        if settings.MOCK_LLM_ENABLED:
            from app.agent.llm_loader import MockChatLLM

            ai_msg = MockChatLLM().invoke([system] + conversation)
            content = _extract_text(ai_msg.content)
        else:
            content = (
                "The configured language-model provider is unavailable. "
                "Please check provider credentials, quota, or configuration."
            )
            ai_msg = AIMessage(content=content)

    final_sources = verified_sources
    if "does not provide enough information" in content.lower() or "knowledge base does not contain" in content.lower():
        final_sources = []
        unique_source_names = []

    return {
        "messages": [ai_msg],
        "response": content,
        "sources": unique_source_names,
        "retrieved_sources": unique_source_names,
        "retrieved_documents": final_sources,
        "structured_sources": final_sources,
    }
