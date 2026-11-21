"""
Comprehensive tests for the stateful Onboarding Supervisor workflow.

Tests verify:
1. Incomplete persona detection and clarification asking.
2. New onboarding session initialization with personalized plan generation.
3. Task completion requiring confirmation/evidence without false positives.
4. Sequential next task transition.
5. Final completion workflow (HR summary + email).
6. Already-completed session rehydration without state degradation.
"""
from datetime import datetime, timezone

import pytest
from langchain_core.messages import HumanMessage, AIMessage

from app.agent.graph import invoke_agent
from app.services.plan_generator import generate_onboarding_plan, persist_onboarding_plan
from app.db.database import SessionLocal
from app.db import models


def test_incomplete_persona_asks_for_missing_info():
    """Verify that an ambiguous or incomplete persona prompt stays in collect_info and asks for details."""
    state = {
        "messages": [HumanMessage(content="Hi, I am joining the team as a developer.")],
        "session_id": "test-incomplete-persona",
        "phase": "greeting",
        "onboarding_complete": False,
    }
    result = invoke_agent(state)

    assert result.get("phase") == "collect_info"
    assert result.get("needs_clarification") is True
    # Verify response asks for clarification
    last_msg = result["messages"][-1].content.lower()
    assert any(k in last_msg for k in ["experience", "level", "stack", "role", "tell"])


def test_new_onboarding_session_generates_plan_and_sets_active_task():
    """Verify a complete introduction initializes persona, builds a personalized plan, and sets Task 1."""
    session_id = "test-new-session-plan"
    db = SessionLocal()
    try:
        db.query(models.ChecklistItemDB).filter(models.ChecklistItemDB.session_id == session_id).delete()
        db.commit()

        state = {
            "messages": [HumanMessage(content="Hello! I am Vikram Desai, joining as a Junior Backend engineer with Python and Django.")],
            "session_id": session_id,
            "phase": "greeting",
            "onboarding_complete": False,
        }
        result = invoke_agent(state)

        assert result.get("role", "").lower() == "backend"
        assert result.get("experience_level", "").lower() == "junior"
        assert result.get("phase") in ("onboarding", "first_task")
        assert "onboarding_plan" in result
        assert len(result["onboarding_plan"]) > 0
        assert result.get("current_task_id") == "JBP-01"
        assert result.get("current_task_index") == 0

        # Verify persisted into DB
        items = db.query(models.ChecklistItemDB).filter(models.ChecklistItemDB.session_id == session_id).all()
        assert len(items) == len(result["onboarding_plan"])
    finally:
        db.query(models.ChecklistItemDB).filter(models.ChecklistItemDB.session_id == session_id).delete()
        db.commit()
        db.close()


def test_task_completion_and_sequential_transition():
    """Verify marking a task complete records completion and advances current_task_id to the next task."""
    session_id = "test-task-progression"
    db = SessionLocal()
    try:
        db.query(models.ChecklistItemDB).filter(models.ChecklistItemDB.session_id == session_id).delete()
        db.commit()

        # Seed plan
        plan = generate_onboarding_plan(
            role="backend",
            experience_level="intern",
            technology_stack=["node.js"],
            session_id=session_id,
        )
        persist_onboarding_plan(db, session_id, plan)

        # 1. Complete Task 1 (BI-01)
        state_step1 = {
            "messages": [HumanMessage(content="I have completed task BI-01. Node 20 and Docker are installed.")],
            "session_id": session_id,
            "phase": "onboarding",
            "current_task_id": "BI-01",
            "onboarding_complete": False,
        }
        result_step1 = invoke_agent(state_step1)

        assert result_step1.get("updated_item_id") == "BI-01"
        assert result_step1.get("updated_item_status") == "Completed"
        assert result_step1.get("completed_count") == 1
        # Next active task should sequentially be BI-02
        assert result_step1.get("current_task_id") == "BI-02"

        # 2. Informational question should NOT inadvertently mark task BI-02 complete
        state_question = {
            "messages": [HumanMessage(content="Where do I find the repository URL for BI-02?")],
            "session_id": session_id,
            "phase": "onboarding",
            "current_task_id": "BI-02",
            "onboarding_complete": False,
        }
        result_question = invoke_agent(state_question)
        # Should remain at 1 completed
        assert result_question.get("completed_count") == 1
        assert result_question.get("current_task_id") == "BI-02"

    finally:
        db.query(models.ChecklistItemDB).filter(models.ChecklistItemDB.session_id == session_id).delete()
        db.commit()
        db.close()


def test_final_completion_triggers_hr_summary_and_email():
    """Verify that when the final task is completed, supervisor routes to HR finalization."""
    session_id = "test-final-completion-flow"
    db = SessionLocal()
    try:
        db.query(models.ChecklistItemDB).filter(models.ChecklistItemDB.session_id == session_id).delete()
        db.commit()

        # Seed plan
        plan = generate_onboarding_plan(
            role="devops",
            experience_level="junior",
            technology_stack=["aws"],
            session_id=session_id,
        )
        persist_onboarding_plan(db, session_id, plan)

        # Mark all but the last task complete in DB
        items = db.query(models.ChecklistItemDB).filter(models.ChecklistItemDB.session_id == session_id).all()
        # Progress is evidence-aware, so seed completions the way the API records them.
        for itm in items[:-1]:
            itm.status = "Completed"
            itm.completion_evidence = "Verified during test"
            itm.completion_source = "user_confirmation"
            itm.completed_at = datetime.now(timezone.utc)
        db.commit()

        last_item_id = items[-1].id.split("::")[-1]

        # Complete the final task
        state_final = {
            "messages": [HumanMessage(content=f"I have finished the last task {last_item_id}. Everything is done.")],
            "session_id": session_id,
            "phase": "onboarding",
            "current_task_id": last_item_id,
            "onboarding_complete": False,
        }
        result_final = invoke_agent(state_final)

        assert result_final.get("onboarding_complete") is True
        assert result_final.get("onboarding_status") == "completed"
        assert result_final.get("phase") == "completed"
        assert result_final.get("hr_notification_status") in ("sent", "mock", "skipped", "error", "failed")

    finally:
        db.query(models.ChecklistItemDB).filter(models.ChecklistItemDB.session_id == session_id).delete()
        db.commit()
        db.close()


def test_already_completed_session_resumes_cleanly():
    """Verify an already completed session rehydrates and answers questions without resetting status."""
    session_id = "test-already-completed-resumption"
    db = SessionLocal()
    try:
        db.query(models.ChecklistItemDB).filter(models.ChecklistItemDB.session_id == session_id).delete()
        db.query(models.OnboardingSessionDB).filter(models.OnboardingSessionDB.session_id == session_id).delete()
        db.commit()

        # Create completed session record
        session_row = models.OnboardingSessionDB(
            session_id=session_id,
            employee_email="test@novabyte.com",
            persona_match="BE-JR-PY",
            status="Completed",
            current_phase="completed",
        )
        db.add(session_row)

        plan = generate_onboarding_plan(
            role="backend",
            experience_level="junior",
            technology_stack=["python"],
            session_id=session_id,
        )
        for task in plan.tasks:
            task.status = "Completed"
        persist_onboarding_plan(db, session_id, plan)

        # Query agent on completed session
        state = {
            "messages": [HumanMessage(content="What is our policy on remote work equipment?")],
            "session_id": session_id,
        }
        result = invoke_agent(state)

        assert result.get("onboarding_complete") is True
        assert result.get("onboarding_status") == "completed"
        assert result.get("progress_percentage") == 100.0
        assert len(result["messages"]) >= 2
    finally:
        db.query(models.ChecklistItemDB).filter(models.ChecklistItemDB.session_id == session_id).delete()
        db.query(models.OnboardingSessionDB).filter(models.OnboardingSessionDB.session_id == session_id).delete()
        db.commit()
        db.close()
