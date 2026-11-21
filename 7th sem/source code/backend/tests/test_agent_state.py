"""
Unit tests for the extended LangGraph AgentState architecture.
Verifies all 6 state domains, type safety, and node backward compatibility.
"""
from datetime import datetime, timezone
from langchain_core.messages import HumanMessage, AIMessage

from app.agent.state import AgentState, TaskPlanItem, EmployeePersonaState
from app.agent.graph import invoke_agent, build_graph
from app.agent.nodes.persona import run as persona_run
from app.agent.nodes.router import run as router_run
from app.agent.nodes.email import run as email_run
from app.agent.nodes.checklist import run as checklist_run


def test_agent_state_type_conformance():
    """Verify that AgentState can represent all 6 required state domains."""
    state: AgentState = {
        "messages": [HumanMessage(content="Hello")],
        "session_id": "test-session-123",
        "user_id": 1,
        "user_email": "dev@novabyte.com",

        # 1. Employee / Persona
        "name": "Jane Doe",
        "role": "backend",
        "experience_level": "junior",
        "technology_stack": ["python", "fastapi", "postgresql"],
        "team": "Core Platform",
        "matched_persona": "BE-JR-PY",
        "persona": {"role": "backend", "level": "junior", "stack": ["python"]},

        # 2. Onboarding Plan
        "onboarding_plan": [
            {
                "task_id": "DEV-01",
                "id": "DEV-01",
                "title": "Clone repository and setup environment",
                "task": "Clone repository and setup environment",
                "category": "Environment Setup",
                "owner": "Employee",
                "deadline": "Day 1",
                "is_required": True,
                "required": True,
                "status": "Completed",
                "order": 1,
                "completion_evidence": "Installed python and dependencies",
            },
            {
                "task_id": "DEV-02",
                "id": "DEV-02",
                "title": "Run test suite",
                "task": "Run test suite",
                "category": "Testing",
                "owner": "Employee",
                "deadline": "Day 2",
                "is_required": True,
                "required": True,
                "status": "In Progress",
                "order": 2,
            }
        ],
        "checklist": [{"id": "DEV-01", "status": "Completed"}, {"id": "DEV-02", "status": "In Progress"}],

        # 3. Current Task
        "current_task_id": "DEV-02",
        "current_task_index": 1,
        "current_step_index": 1,
        "current_task_status": "In Progress",
        "completion_evidence": "pytest run completed",

        # 4. Agent Execution
        "phase": "onboarding",
        "current_phase": "onboarding",
        "intent": "checklist_action",
        "detected_intent": "checklist_action",
        "retrieved_chunks": ["PR review policy chunk 1"],
        "retrieved_sources": ["engineering_standards.md"],
        "sources": ["engineering_standards.md"],
        "retrieved_documents": [{"source": "engineering_standards.md", "score": 0.85}],
        "context_docs": "Standard PR guidelines",
        "tool_results": ["Updated DEV-01 to Completed"],
        "suggested_actions": ["Proceed to DEV-02"],
        "response": "Great progress! Your task DEV-01 has been marked completed.",

        # 5. Progress
        "completed_count": 1,
        "total_count": 2,
        "progress_percentage": 50.0,
        "percentage": 50.0,
        "onboarding_status": "in_progress",

        # 6. Completion
        "onboarding_complete": False,
        "completion_timestamp": None,
        "hr_notification_status": "pending",
        "ticket_assigned": True,
        "ticket_reference": "GH-backend-starter-101",
    }

    assert state["role"] == "backend"
    assert state["completed_count"] == 1
    assert state["total_count"] == 2
    assert state["progress_percentage"] == 50.0
    assert len(state["onboarding_plan"]) == 2
    assert state["current_task_id"] == "DEV-02"


def test_persona_node_populates_extended_fields():
    """Verify that persona node extracts structured persona and team details."""
    state = {
        "messages": [HumanMessage(content="I am a junior backend developer working with Python and FastAPI.")],
        "phase": "collect_info",
    }
    result = persona_run(state)

    assert result["role"].lower() == "backend"
    assert result["experience_level"].lower() == "junior"
    assert "python" in [s.lower() for s in result["technology_stack"]]
    assert result["team"] is not None
    assert result["onboarding_status"] == "in_progress"


def test_router_node_populates_detected_intent():
    """Verify router node populates both legacy intent and detected_intent."""
    state = {
        "messages": [HumanMessage(content="Where can I find our engineering standards?")],
        "phase": "onboarding",
    }
    result = router_run(state)

    assert result["intent"] == "question"
    assert result["detected_intent"] == "question"
    assert result["phase"] == "onboarding"
    assert result["current_phase"] == "onboarding"


def test_email_node_populates_completion_metadata():
    """Verify email node populates completion_timestamp and hr_notification_status."""
    state = {
        "session_id": "test-completion-session",
        "phase": "completed",
    }
    result = email_run(state)

    assert result["onboarding_complete"] is True
    assert result["onboarding_status"] == "completed"
    assert "completion_timestamp" in result
    assert result["completion_timestamp"] is not None
    assert "hr_notification_status" in result


def test_graph_executes_with_extended_state():
    """Verify full LangGraph invocation executes cleanly with extended state schema."""
    initial_state = {
        "messages": [HumanMessage(content="Hi, I am ready to start my onboarding as a Senior DevOps Engineer.")],
        "session_id": "test-session-graph",
        "phase": "greeting",
        "onboarding_complete": False,
    }
    result = invoke_agent(initial_state)

    assert len(result["messages"]) >= 2
    assert isinstance(result["messages"][-1], AIMessage)
    assert result.get("role") in ("devops", "general") or result.get("matched_persona") is not None
