"""Questions must reach the RAG node with the user's persona, whatever phase or wording they use."""
import uuid

import pytest
from langchain_core.messages import HumanMessage

import app.rag.retriever as retriever
from app.agent.graph import graph
from app.agent.nodes.composer import run as composer_run
from app.agent.nodes.router import run as router_run
from app.agent.nodes.session_loader import run as session_loader_run
from app.db import models
from app.db.database import SessionLocal
from app.services.plan_generator import apply_onboarding_plan

INSUFFICIENT = "does not provide enough information"


@pytest.mark.parametrize("text, intent", [
    ("What is the PR review policy?", "question"),
    ("Where do I find the repository URL for BI-02?", "question"),
    ("What is the first task I should do and how do I set up the repo?", "question"),
    ("Is BI-02 done?", "question"),
    ("I am stuck on BI-03, how do I get VPN access?", "question"),
    ("I have finished task BI-01: Node.js 20 is installed", "checklist_action"),
    ("Can you mark BI-02 as done?", "checklist_action"),
    ("set BI-03 to in progress", "checklist_action"),
    ("BI-04 is blocked, waiting on access", "checklist_action"),
    ("What is my progress?", "checklist_action"),
    ("show my checklist", "checklist_action"),
    ("finish onboarding", "complete"),
])
def test_router_separates_questions_from_task_updates(text, intent):
    assert router_run({"messages": [HumanMessage(content=text)], "phase": "onboarding"})["intent"] == intent


def test_greeting_phase_question_is_answered_not_deflected():
    result = router_run({"messages": [HumanMessage(content="What is the PR review policy?")], "phase": "greeting"})
    assert result == {"intent": "question", "phase": "greeting"}
    intro = router_run({"messages": [HumanMessage(content="Hi, I am a backend intern")], "phase": "greeting"})
    assert intro["intent"] == "intro"


@pytest.fixture
def session():
    sid = f"rag-routing-{uuid.uuid4().hex[:6]}"
    db = SessionLocal()
    db.add(models.OnboardingSessionDB(session_id=sid, employee_email="rag@novabyte.io", persona_match="riya_sharma",
                                      status="In Progress", current_phase="onboarding"))
    db.commit()
    apply_onboarding_plan(db, sid, "backend", "intern", ["node.js"])
    db.close()
    yield sid
    db = SessionLocal()
    db.query(models.ChecklistItemDB).filter(models.ChecklistItemDB.session_id == sid).delete()
    db.query(models.OnboardingSessionDB).filter(models.OnboardingSessionDB.session_id == sid).delete()
    db.commit()
    db.close()


def test_session_loader_restores_persona_for_retrieval(session):
    state = session_loader_run({"session_id": session})
    assert state["persona"]["persona_id"] == "riya_sharma"
    assert state["role"] == "backend"
    assert "node.js" in state["technology_stack"]


def test_question_reaches_rag_with_persona_on_later_turns(session, monkeypatch):
    seen = {}
    original = retriever.retrieve_context

    def spy(query, k=4, filter=None, persona=None):
        seen["persona"] = persona
        return original(query, k=k, filter=filter, persona=persona)

    monkeypatch.setattr(retriever, "retrieve_context", spy)
    state = {"messages": [HumanMessage(content="Where do I find the repository URL for BI-02?")],
             "session_id": session, "phase": "onboarding", "onboarding_complete": False}
    nodes, final = [], {}
    for event in graph.stream(state):
        for node, out in event.items():
            nodes.append(node)
            final.update(out or {})

    assert "rag" in nodes and "checklist" not in nodes
    assert seen["persona"]["role"] == "backend"
    assert final["retrieved_sources"]


def test_task_question_without_kb_match_uses_task_details():
    state = {
        "intent": "question",
        "messages": [HumanMessage(content="Is BI-02 done?")],
        "context_docs": "",
        "checklist": [{"task_id": "BI-02", "title": "Repository Access", "description": "Clone the repo", "status": "Pending"}],
    }
    assert INSUFFICIENT not in composer_run(state)["response"].lower()


def test_unrelated_question_still_declines():
    state = {"intent": "question", "messages": [HumanMessage(content="What's the weather in Paris?")], "context_docs": "",
             "checklist": [{"task_id": "BI-02", "title": "Repository Access", "status": "Pending"}]}
    assert INSUFFICIENT in composer_run(state)["response"].lower()


def test_composer_shows_only_the_verified_sources_line(monkeypatch):
    from langchain_core.language_models.fake_chat_models import FakeListChatModel
    import app.agent.nodes.composer as composer

    reply = "You need 2 approvals.\n\n**Sources:** onboarding_faq.md, made_up_doc.md"
    monkeypatch.setattr(composer, "get_llm", lambda *a, **k: FakeListChatModel(responses=[reply]))
    state = {
        "intent": "question",
        "messages": [HumanMessage(content="How many approvals does my PR need?")],
        "context_docs": "### [onboarding_faq.md] Q18\nMinimum 2 approvals.",
        "structured_sources": [{"source": "onboarding_faq.md", "section": "Q18"}],
    }
    response = composer.run(state)["response"]
    assert response.lower().count("sources:") == 1
    assert "made_up_doc.md" not in response
    assert response.endswith("*Sources: onboarding_faq.md*")


def test_saved_error_notices_are_not_fed_back_to_the_model(monkeypatch):
    """A model shown its own past error notices starts repeating them verbatim."""
    from langchain_core.language_models.fake_chat_models import FakeListChatModel
    from langchain_core.messages import AIMessage
    import app.agent.nodes.composer as composer

    sent = {}

    class Recorder(FakeListChatModel):
        def invoke(self, messages, *args, **kwargs):
            sent["messages"] = messages
            return super().invoke(messages, *args, **kwargs)

    monkeypatch.setattr(composer, "get_llm", lambda *a, **k: Recorder(responses=["Hello! What's your role?"]))
    notice = "The configured language-model provider is unavailable. Please check provider credentials, quota, or configuration."
    history = [AIMessage(content="Welcome to NovaByte!")]
    for _ in range(3):
        history += [HumanMessage(content="hi"), AIMessage(content=notice)]
    history.append(HumanMessage(content="hi"))

    composer.run({"intent": "greeting", "messages": history})

    contents = [str(m.content) for m in sent["messages"]]
    assert not any(c.startswith("The configured language-model provider") for c in contents)
    assert "Welcome to NovaByte!" in contents  # real assistant turns are kept
