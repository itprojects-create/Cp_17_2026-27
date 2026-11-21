import json
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.utils import get_current_user, require_admin
from app.db.database import get_db
from app.db.models import OnboardingSessionDB, UserDB
from app.rag.retriever import retrieve_context

logger = logging.getLogger(__name__)

NO_ANSWER = "The knowledge base does not provide enough information to answer this question."

router = APIRouter()

KB_DIR = Path(__file__).resolve().parents[2] / "knowledge_base"


def _first_heading(content: str) -> Optional[str]:
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("#"):
            return line.lstrip("#").strip()
    return None


def _category_from_stem(stem: str) -> str:
    mapping = {
        "company_overview": "Getting Started",
        "setup_guides": "Getting Started",
        "engineering_standards": "Coding Standards",
        "architecture_documentation": "Architecture",
        "policies": "Security",
        "org_structure": "Organization",
        "onboarding_faq": "FAQ",
    }
    return mapping.get(stem, "General")


# Per-article details that don't belong in the Markdown itself (it is embedded for search as-is).
META_FILE = "_metadata.json"


def _read_meta() -> dict:
    try:
        return json.loads((KB_DIR / META_FILE).read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return {}


def _write_meta(meta: dict) -> None:
    (KB_DIR / META_FILE).write_text(json.dumps(meta, indent=2, sort_keys=True), encoding="utf-8")


def _load_articles() -> list[dict]:
    articles: list[dict] = []
    if not KB_DIR.exists():
        return articles

    meta = _read_meta()
    for file in sorted(KB_DIR.glob("*.md")):
        content = file.read_text(encoding="utf-8")
        stem = file.stem
        title = _first_heading(content) or stem.replace("_", " ").title()
        info = meta.get(stem, {})

        articles.append(
            {
                "id": stem,
                "title": title,
                "content": content,
                "category": info.get("category") or _category_from_stem(stem),
                "tags": stem.split("_"),
                "updated_at": file.stat().st_mtime,
                "updated_by": info.get("updated_by"),
            }
        )

    return articles


def _fallback_answer_from_articles(query: str, articles: list[dict]) -> tuple[str, list[dict]]:
    terms = [t for t in query.lower().split() if len(t) > 2]
    ranked = []
    for article in articles:
        hay = f"{article['title']} {article['content']}".lower()
        score = sum(1 for t in terms if t in hay)
        if score > 0:
            ranked.append((score, article))

    ranked.sort(key=lambda x: x[0], reverse=True)
    top = [a for _, a in ranked[:3]]

    if not top:
        return "I could not find relevant documentation for that query.", []

    chunks = []
    citations = []
    for article in top:
        snippet = article["content"].strip().replace("\n\n", "\n")
        chunks.append(f"{article['title']}:\n{snippet[:700]}")
        citations.append({"source": f"knowledge_base/{article['id']}.md", "score": 0.0})

    return "\n\n".join(chunks), citations


@router.get("/knowledge/articles")
def list_knowledge_articles(
    q: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    current_user: UserDB = Depends(get_current_user),
):
    _ = current_user
    articles = _load_articles()

    if category:
        articles = [a for a in articles if a["category"].lower() == category.lower()]

    if q:
        needle = q.lower()
        articles = [
            a
            for a in articles
            if needle in a["title"].lower()
            or needle in a["content"].lower()
            or any(needle in t.lower() for t in a["tags"])
        ]

    return {"articles": articles}


@router.get("/knowledge/articles/{article_id}")
def get_knowledge_article(article_id: str, current_user: UserDB = Depends(get_current_user)):
    _ = current_user
    articles = _load_articles()
    article = next((a for a in articles if a["id"] == article_id), None)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return article


# ─── Admin document management ───

class ArticlePayload(BaseModel):
    title: str
    content: str
    category: str = "General"


MAX_TITLE_CHARS = 120
MAX_CATEGORY_CHARS = 40
MAX_CONTENT_CHARS = 200_000
ARTICLE_ID_PATTERN = re.compile(r"^[a-z0-9_]{1,64}$")

# File writes and re-indexing must not interleave between concurrent admin edits.
_kb_write_lock = threading.Lock()


def _slugify(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")[:64]


def _article_path(article_id: str) -> Path:
    if not ARTICLE_ID_PATTERN.match(article_id):
        raise HTTPException(status_code=404, detail="Article not found")
    return KB_DIR / f"{article_id}.md"


def _validated(payload: ArticlePayload) -> tuple[str, str, str]:
    title = payload.title.strip()
    category = payload.category.strip() or "General"
    body = payload.content.strip()
    if not title or len(title) > MAX_TITLE_CHARS:
        raise HTTPException(status_code=400, detail=f"Title is required (max {MAX_TITLE_CHARS} characters)")
    if len(category) > MAX_CATEGORY_CHARS:
        raise HTTPException(status_code=400, detail=f"Category must be at most {MAX_CATEGORY_CHARS} characters")
    if not body:
        raise HTTPException(status_code=400, detail="Content is required")
    if len(body) > MAX_CONTENT_CHARS:
        raise HTTPException(status_code=400, detail="Document is too large (max 200,000 characters)")

    # The title is stored as the document's H1, replacing one the content already starts with.
    lines = body.splitlines()
    if lines and lines[0].startswith("# "):
        body = "\n".join(lines[1:]).strip()
    return title, category, f"# {title}\n\n{body}\n"


def _save_article(article_id: str, markdown: str, category: str, admin: UserDB) -> dict:
    """Write the file and its metadata, then re-index it. Caller holds the write lock."""
    from app.rag.ingest import reindex_document

    path = _article_path(article_id)
    KB_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown, encoding="utf-8")

    meta = _read_meta()
    meta[article_id] = {
        "category": category,
        "updated_by": admin.username,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    _write_meta(meta)

    indexed = True
    try:
        reindex_document(path)
    except Exception as exc:
        # The document is saved and browsable; search falls back to keywords until the next re-index.
        indexed = False
        logger.warning("Re-indexing %s failed: %s", path.name, exc)

    article = next(a for a in _load_articles() if a["id"] == article_id)
    return {**article, "indexed": indexed}


@router.post("/knowledge/articles", status_code=201)
def create_knowledge_article(payload: ArticlePayload, admin: UserDB = Depends(require_admin)):
    title, category, markdown = _validated(payload)
    article_id = _slugify(title)
    if not article_id:
        raise HTTPException(status_code=400, detail="Title must contain letters or digits")
    with _kb_write_lock:
        if _article_path(article_id).exists():
            raise HTTPException(status_code=409, detail="An article with this title already exists")
        article = _save_article(article_id, markdown, category, admin)
    logger.info("HR admin %s created knowledge article %s", admin.username, article_id)
    return article


@router.put("/knowledge/articles/{article_id}")
def update_knowledge_article(article_id: str, payload: ArticlePayload, admin: UserDB = Depends(require_admin)):
    title, category, markdown = _validated(payload)
    with _kb_write_lock:
        if not _article_path(article_id).exists():
            raise HTTPException(status_code=404, detail="Article not found")
        article = _save_article(article_id, markdown, category, admin)
    logger.info("HR admin %s updated knowledge article %s", admin.username, article_id)
    return article


@router.delete("/knowledge/articles/{article_id}")
def delete_knowledge_article(article_id: str, admin: UserDB = Depends(require_admin)):
    from app.rag.ingest import remove_document_chunks

    with _kb_write_lock:
        path = _article_path(article_id)
        if not path.exists():
            raise HTTPException(status_code=404, detail="Article not found")
        path.unlink()
        meta = _read_meta()
        if meta.pop(article_id, None) is not None:
            _write_meta(meta)
        try:
            remove_document_chunks(path.name)
        except Exception as exc:
            logger.warning("Removing %s from the search index failed: %s", path.name, exc)
    logger.info("HR admin %s deleted knowledge article %s", admin.username, article_id)
    return {"deleted": article_id}


def _user_persona(db: Session, user: UserDB) -> Optional[dict]:
    """Persona of the user's latest onboarding session, so answers favour their role and stack."""
    from app.agent.nodes.session_loader import _persona_state

    session = (
        db.query(OnboardingSessionDB)
        .filter(OnboardingSessionDB.user_id == user.id)
        .order_by(OnboardingSessionDB.started_at.desc())
        .first()
    )
    if not session or not session.persona_match:
        return None
    return _persona_state(session.persona_match).get("persona")


def _unique_citations(citations: list[dict]) -> list[dict]:
    """One entry per source section, with the fields the UI needs to link to the article."""
    seen, unique = set(), []
    for c in citations:
        source = str(c.get("source") or "")
        key = (source, c.get("section"))
        if not source or key in seen:
            continue
        seen.add(key)
        unique.append({
            "source": source,
            "article_id": Path(source).stem,
            "section": c.get("section") or None,
            "title": c.get("title") or None,
            "score": c.get("score", 0.0),
        })
    return unique


def _generate_answer(query: str, context: str) -> Optional[str]:
    """Write a grounded answer from the retrieved context, or None if no LLM is available."""
    from app.agent.llm_loader import get_llm
    from app.agent.nodes.composer import SYSTEM_PROMPT, _extract_text

    try:
        llm = get_llm()
        # Same grounding rules and prompt layout as the chat composer.
        system = SystemMessage(content=SYSTEM_PROMPT + f"\nIntent: question\n\nContext:\n{context}")
        reply = llm.invoke([system, HumanMessage(content=query)])
        answer = _extract_text(reply.content if isinstance(reply, AIMessage) else getattr(reply, "content", reply)).strip()
        return answer or None
    except Exception as exc:
        logger.warning("Knowledge answer generation unavailable, returning excerpts: %s", exc)
        return None


@router.post("/knowledge/ask")
def ask_knowledge(payload: dict, db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    """
    Answer a question from the knowledge base.

    Response `mode`:
      - "ai":       an LLM-written answer grounded in the cited documents
      - "excerpts": the LLM is unavailable, so the matching passages are returned verbatim
      - "none":     nothing relevant was found
    """
    query = (payload.get("query") or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query is required")

    persona = _user_persona(db, current_user)
    context = ""
    citations: list[dict] = []

    # Keep API responsive even if vector retrieval is slow/unavailable.
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(retrieve_context, query, 4, None, persona)
    try:
        result = future.result(timeout=6)
        context = result.get("context", "")
        citations = result.get("citations", [])
    except (FuturesTimeoutError, Exception):
        context, citations = _fallback_answer_from_articles(query, _load_articles())
        if not citations:
            context = ""
    finally:
        # Do not wait for a potentially stuck retrieval thread.
        executor.shutdown(wait=False, cancel_futures=True)

    if not context.strip() or not citations:
        return {"answer": NO_ANSWER, "citations": [], "mode": "none"}

    sources = _unique_citations(citations)
    answer = _generate_answer(query, context)
    if answer is None:
        return {"answer": context, "citations": sources, "mode": "excerpts"}

    # The model declined: don't attach sources to a non-answer.
    if "does not provide enough information" in answer.lower():
        return {"answer": answer, "citations": [], "mode": "none"}
    return {"answer": answer, "citations": sources, "mode": "ai"}
