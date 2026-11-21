"""
Golden Test Suite for NovaByte Onboarding Agent Behavior.
Tests persona extraction, intent classification, clarification handling,
bonus integrations, and RAG context retrieval across representative scenarios.
"""
import pytest
from langchain_core.messages import HumanMessage
from app.agent.nodes import router_run, persona_run, rag_run, ticket_run, email_run
from app.services.persona_matcher import extract_user_profile, identify_persona


# ---------------------------------------------------------------------------
# 1. Persona Extraction Golden Tests (Table-driven)
# ---------------------------------------------------------------------------

PERSONA_CASES = [
    (
        "Hi, I'm Riya, Backend Intern working on Node.js and TypeScript",
        "backend",
        "intern",
        ["node", "typescript"],
    ),
    (
        "Hello, I am a Senior Frontend Engineer with extensive React and Vue experience",
        "frontend",
        "senior",
        ["react", "vue"],
    ),
    (
        "Hey! Joining as a Junior DevOps engineer using Docker and Kubernetes",
        "devops",
        "junior",
        ["docker", "kubernetes"],
    ),
    (
        "I'm an ML Intern focused on Python and PyTorch models",
        "ml",
        "intern",
        ["python", "pytorch"],
    ),
    (
        "Fullstack Senior developer specializing in Python, FastAPI, and Next.js",
        "fullstack",
        "senior",
        ["python", "fastapi", "next.js"],
    ),
]


@pytest.mark.parametrize("input_text,expected_role,expected_level,expected_stacks", PERSONA_CASES)
def test_persona_extraction_table(input_text, expected_role, expected_level, expected_stacks):
    profile = extract_user_profile(input_text)
    assert profile.get("role") == expected_role, f"Expected role {expected_role}, got {profile.get('role')}"
    assert profile.get("level") == expected_level, f"Expected level {expected_level}, got {profile.get('level')}"
    
    extracted_stacks = [s.lower() for s in profile.get("tech_stack", [])]
    for expected_stack in expected_stacks:
        assert any(expected_stack in s for s in extracted_stacks), (
            f"Expected {expected_stack} in {extracted_stacks}"
        )


# ---------------------------------------------------------------------------
# 2. Incomplete / Ambiguous Input Clarification Tests
# ---------------------------------------------------------------------------

AMBIGUOUS_CASES = [
    "Hi, I'm joining as a developer.",
    "I am an intern here.",
    "Hello team, excited to be here!",
]


@pytest.mark.parametrize("ambiguous_text", AMBIGUOUS_CASES)
def test_persona_node_requires_clarification_for_incomplete_input(ambiguous_text):
    state = {
        "phase": "collect_info",
        "messages": [HumanMessage(content=ambiguous_text)],
    }
    result = persona_run(state)
    assert result.get("phase") == "collect_info"
    assert result.get("needs_clarification") is True
    assert result.get("onboarding_status") == "pending"
    assert len(result.get("suggested_actions", [])) > 0


# ---------------------------------------------------------------------------
# 3. Router Intent Classification Golden Tests (Table-driven)
# ---------------------------------------------------------------------------

ROUTER_CASES = [
    ("complete onboarding", "collect_info", "complete", "completed"),
    ("finish onboarding now please", "collect_info", "complete", "completed"),
    ("NB-102 done", "onboarding", "checklist_action", "onboarding"),
    ("mark DEV-01 complete", "onboarding", "checklist_action", "onboarding"),
    ("What's our PR review policy?", "onboarding", "question", "onboarding"),
    ("Where do I find the database credentials and architecture docs?", "onboarding", "question", "onboarding"),
    ("Hello! I am a backend intern with Python experience", "collect_info", "intro", "first_task"),
]


@pytest.mark.parametrize("input_text,current_phase,expected_intent,expected_phase", ROUTER_CASES)
def test_router_intent_transitions(input_text, current_phase, expected_intent, expected_phase):
    state = {
        "phase": current_phase,
        "messages": [HumanMessage(content=input_text)],
    }
    result = router_run(state)
    assert result["intent"] == expected_intent, f"For '{input_text}', expected intent {expected_intent}, got {result['intent']}"
    assert result["phase"] == expected_phase, f"For '{input_text}', expected phase {expected_phase}, got {result['phase']}"


# ---------------------------------------------------------------------------
# 4. RAG Node Knowledge Retrieval Tests
# ---------------------------------------------------------------------------

def test_rag_retrieves_relevant_knowledge_context():
    state = {
        "phase": "onboarding",
        "intent": "question",
        "messages": [HumanMessage(content="What are the coding standards, PR review policies, and guidelines?")],
    }
    result = rag_run(state)
    assert "context_docs" in result
    assert len(result["context_docs"]) > 0
    # Check that sources are cited
    assert "retrieved_sources" in result
    assert len(result["retrieved_sources"]) > 0
    for src in result["retrieved_sources"]:
        assert not src.endswith("§1"), f"Source citation should not contain fake §1: {src}"


# ---------------------------------------------------------------------------
# 5. Bonus Integrations Execution in Agent Nodes
# ---------------------------------------------------------------------------

def test_ticket_node_assigns_integration_ticket():
    state = {
        "phase": "first_task",
        "persona": {"role": "backend", "level": "intern", "stack": ["python"]},
        "ticket_assigned": False,
    }
    result = ticket_run(state)
    assert result["ticket_assigned"] is True
    assert "ticket_reference" in result
    assert len(result["ticket_reference"]) > 0
    assert any("Starter ticket" in a for a in result.get("suggested_actions", []))


def test_persona_node_sends_no_slack_welcome():
    """Slack was removed: generating a plan must not report or attempt a Slack welcome."""
    state = {
        "phase": "collect_info",
        "messages": [HumanMessage(content="I am a backend junior engineer specializing in python and fastapi")],
    }
    result = persona_run(state)
    assert result["phase"] == "onboarding"
    assert result["onboarding_status"] == "in_progress"
    assert "slack_welcome_sent" not in result


def test_ticket_node_uses_github_for_every_role():
    for role in ("backend", "frontend", "ml", "fullstack"):
        result = ticket_run({"persona": {"role": role, "level": "junior", "stack": []}, "ticket_assigned": False})
        assert result["ticket_reference"].startswith("GH-") or "github" in result["ticket_reference"].lower()


# ---------------------------------------------------------------------------
# 6. Email Node Execution
# ---------------------------------------------------------------------------

def test_email_node_marks_completion_safely():
    state = {
        "session_id": "demo-session",
        "phase": "completed",
    }
    result = email_run(state)
    assert result["onboarding_complete"] is True
    assert result["phase"] == "completed"
    assert len(result.get("tool_results", [])) > 0
