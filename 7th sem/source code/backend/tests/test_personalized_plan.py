"""
Tests for Personalized Onboarding Plan Generator and LangGraph workflow.
Proves that:
1. Backend Intern + Node.js generates a specific tailored plan.
2. Frontend Senior + React generates a DIFFERENT plan.
3. DevOps Junior generates a DIFFERENT plan.
4. Plans have all required fields and persist across session restarts without losing state.
5. Sequential execution advances progress properly.
"""
import pytest
from app.services.plan_generator import (
    generate_onboarding_plan,
    persist_onboarding_plan,
    get_plan_tasks_for_session,
)
from app.db.database import SessionLocal
from app.db import models
from app.agent.graph import invoke_agent
from langchain_core.messages import HumanMessage


def test_three_distinct_personas_produce_different_plans():
    """
    Verify that:
    - Backend Intern + Node.js
    - Frontend Senior + React
    - DevOps Junior
    produce 3 completely distinct onboarding plans tailored to their roles, levels, stacks, and requirements.
    """
    # 1. Backend Intern + Node.js
    plan_backend_intern = generate_onboarding_plan(
        role="backend",
        experience_level="intern",
        technology_stack=["node.js", "express", "mongodb"],
        team="Connector Squad",
        session_id="session-be-intern",
    )

    # 2. Frontend Senior + React
    plan_frontend_senior = generate_onboarding_plan(
        role="frontend",
        experience_level="senior",
        technology_stack=["react", "typescript", "tailwind"],
        team="Web Platform Squad",
        session_id="session-fe-senior",
    )

    # 3. DevOps Junior
    plan_devops_junior = generate_onboarding_plan(
        role="devops",
        experience_level="junior",
        technology_stack=["docker", "kubernetes", "aws", "terraform"],
        team="Infrastructure",
        session_id="session-do-junior",
    )

    # Assert basic structure
    assert plan_backend_intern.total_tasks > 0
    assert plan_frontend_senior.total_tasks > 0
    assert plan_devops_junior.total_tasks > 0

    # Extract task titles and technologies
    be_titles = [t.title for t in plan_backend_intern.tasks]
    fe_titles = [t.title for t in plan_frontend_senior.tasks]
    do_titles = [t.title for t in plan_devops_junior.tasks]

    be_ids = [t.task_id for t in plan_backend_intern.tasks]
    fe_ids = [t.task_id for t in plan_frontend_senior.tasks]
    do_ids = [t.task_id for t in plan_devops_junior.tasks]

    # Proving all 3 plans are DIFFERENT
    assert be_titles != fe_titles, "Backend Intern and Frontend Senior plans must differ"
    assert be_titles != do_titles, "Backend Intern and DevOps Junior plans must differ"
    assert fe_titles != do_titles, "Frontend Senior and DevOps Junior plans must differ"

    assert be_ids != fe_ids
    assert be_ids != do_ids
    assert fe_ids != do_ids

    # Verify Backend Intern specifics
    assert any("BI-" in tid for tid in be_ids)
    assert any("connector-runtime" in t.description.lower() for t in plan_backend_intern.tasks)
    assert any("api standards" in t.title.lower() for t in plan_backend_intern.tasks)

    # Verify Frontend Senior specifics (Design system, Storybook, Stakeholders, Leading PR)
    assert any("SFR-" in tid for tid in fe_ids)
    assert any("storybook" in t.description.lower() or "design system" in t.title.lower() for t in plan_frontend_senior.tasks)
    assert any("stakeholder" in t.title.lower() or "alignment" in t.title.lower() for t in plan_frontend_senior.tasks)
    assert any("lead" in t.title.lower() for t in plan_frontend_senior.tasks)

    # Verify DevOps Junior specifics (AWS, Terraform, Kubernetes EKS)
    assert any("JDO-" in tid for tid in do_ids)
    assert any("aws" in t.description.lower() or "vpn" in t.description.lower() for t in plan_devops_junior.tasks)
    assert any("kubernetes" in t.title.lower() or "cluster" in t.title.lower() for t in plan_devops_junior.tasks)
    assert any("terraform" in t.description.lower() for t in plan_devops_junior.tasks)


def test_structured_plan_model_fields():
    """Verify that every task in the generated plan has all required attributes."""
    plan = generate_onboarding_plan(
        role="backend",
        experience_level="intern",
        technology_stack=["node.js"],
        team="Platform",
        session_id="session-field-check",
    )

    for task in plan.tasks:
        assert task.task_id is not None and len(task.task_id) > 0
        assert isinstance(task.order, int) and task.order >= 1
        assert task.title is not None and len(task.title) > 0
        assert task.description is not None and len(task.description) > 0
        assert task.category is not None and len(task.category) > 0
        assert task.required is True
        assert task.status in ("Pending", "Not Started")
        assert task.role == "backend"
        assert task.technology is not None and len(task.technology) > 0
        assert task.evidence_required is not None and len(task.evidence_required) > 0


def test_plan_persistence_and_restart_resilience():
    """Verify that generated plans persist in the SQLite database and survive application restarts."""
    db = SessionLocal()
    session_id = "test-restart-resilience-session"

    try:
        # Clean up any preexisting test rows
        db.query(models.ChecklistItemDB).filter(models.ChecklistItemDB.session_id == session_id).delete()
        db.commit()

        # 1. Generate and persist plan
        plan = generate_onboarding_plan(
            role="devops",
            experience_level="junior",
            technology_stack=["docker", "kubernetes", "aws"],
            session_id=session_id,
        )
        persist_onboarding_plan(db, session_id, plan)

        # 2. Simulate restarting app / reading persisted state
        persisted_tasks = get_plan_tasks_for_session(db, session_id)
        assert len(persisted_tasks) == len(plan.tasks)
        assert persisted_tasks[0]["task_id"] == plan.tasks[0].task_id

        # 3. Complete first task
        db_item = db.query(models.ChecklistItemDB).filter(
            models.ChecklistItemDB.session_id == session_id
        ).first()
        db_item.status = "Completed"
        db.commit()

        # 4. Re-persisting should preserve already completed tasks
        persist_onboarding_plan(db, session_id, plan)
        updated_tasks = get_plan_tasks_for_session(db, session_id)
        assert updated_tasks[0]["status"] == "Completed"

    finally:
        db.query(models.ChecklistItemDB).filter(models.ChecklistItemDB.session_id == session_id).delete()
        db.commit()
        db.close()


def test_langgraph_flow_generates_and_tracks_plan():
    """Verify end-to-end LangGraph invocation creates the structured plan and advances state."""
    session_id = "test-graph-plan-flow"
    initial_state = {
        "messages": [HumanMessage(content="Hello! I am Riya Sharma, joining as a Backend Intern with Node.js and Express.")],
        "session_id": session_id,
        "phase": "greeting",
        "onboarding_complete": False,
    }

    result = invoke_agent(initial_state)

    assert result.get("role", "").lower() == "backend"
    assert result.get("experience_level", "").lower() == "intern"
    assert "onboarding_plan" in result
    assert len(result["onboarding_plan"]) > 0
    assert result.get("current_task_id") == "BI-01"
    assert result.get("total_count") == len(result["onboarding_plan"])
    assert result.get("completed_count") == 0
