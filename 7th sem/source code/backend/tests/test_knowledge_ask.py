"""Knowledge Base "Ask AI": grounded answers with citations, and honest fallbacks."""
import uuid

import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import FakeListChatModel

import app.agent.llm_loader as llm_loader
import app.routes.knowledge as knowledge
from app.db import models
from app.db.database import SessionLocal
from app.main import app
from app.routes.auth import limiter

client = TestClient(app)


@pytest.fixture(autouse=True)
def _no_rate_limit():
    limiter.enabled = False
    yield
    limiter.enabled = True


@pytest.fixture
def headers():
    username = f"ask_{uuid.uuid4().hex[:8]}"
    r = client.post("/api/auth/register", json={"username": username, "email": f"{username}@novabyte.io", "password": "Passw0rd!23"})
    assert r.status_code == 200, r.text
    token = client.post("/api/auth/login", data={"username": username, "password": "Passw0rd!23"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def ask(headers, query):
    r = client.post("/api/knowledge/ask", headers=headers, json={"query": query})
    assert r.status_code == 200, r.text
    return r.json()


def test_relevant_question_gets_generated_answer_with_linkable_sources(headers):
    result = ask(headers, "What is the PR review policy?")
    assert result["mode"] == "ai"
    # A generated answer, not the raw retrieved chunks.
    assert "### [" not in result["answer"]
    article_ids = {a["id"] for a in client.get("/api/knowledge/articles", headers=headers).json()["articles"]}
    assert result["citations"]
    assert all(c["article_id"] in article_ids for c in result["citations"])


def test_unrelated_question_returns_no_answer_without_sources(headers):
    result = ask(headers, "best pizza recipe")
    assert result["mode"] == "none"
    assert result["citations"] == []


def test_llm_unavailable_returns_labelled_excerpts(headers, monkeypatch):
    def unavailable(*args, **kwargs):
        raise RuntimeError("Configured LLM is unavailable")

    monkeypatch.setattr(llm_loader, "get_llm", unavailable)
    result = ask(headers, "How do I get GitHub access?")
    assert result["mode"] == "excerpts"
    assert result["citations"]
    assert result["answer"].strip()


def test_model_declining_drops_sources(headers, monkeypatch):
    monkeypatch.setattr(llm_loader, "get_llm", lambda *a, **k: FakeListChatModel(responses=[knowledge.NO_ANSWER]))
    result = ask(headers, "What is the PR review policy?")
    assert result["mode"] == "none"
    assert result["citations"] == []


def test_retrieval_uses_the_askers_persona(headers, monkeypatch):
    me = client.get("/api/auth/me", headers=headers).json()
    db = SessionLocal()
    session = db.query(models.OnboardingSessionDB).filter(models.OnboardingSessionDB.user_id == me["id"]).first()
    session.persona_match = "riya_sharma"
    db.commit()
    db.close()

    seen = {}
    original = knowledge.retrieve_context

    def spy(query, k=4, filter=None, persona=None):
        seen["persona"] = persona
        return original(query, k, filter, persona)

    monkeypatch.setattr(knowledge, "retrieve_context", spy)
    ask(headers, "How do I set up my local environment?")
    assert seen["persona"]["role"] == "Backend"
    assert "node.js" in seen["persona"]["stack"]


def test_empty_query_is_rejected(headers):
    assert client.post("/api/knowledge/ask", headers=headers, json={"query": "  "}).status_code == 400
