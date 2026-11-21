"""
End-to-End automated tests for the three canonical developer onboarding personas:
1. Backend Intern — Node.js
2. Frontend Senior — React
3. DevOps Junior — Python/Docker

For each persona, the test verifies:
- Persona identification
→ Personalized onboarding plan generation
→ Relevant persona-aware RAG retrieval
→ Checklist creation & DB persistence
→ Evidence-aware task progression & sequential transition
→ Starter ticket / tool integration action
→ Completion detection
→ HR summary & completion email generation
"""
from datetime import datetime, timezone

import pytest
from langchain_core.messages import HumanMessage

from app.config import settings
from app.agent.graph import invoke_agent
from app.db.database import SessionLocal
from app.db import models
from app.rag.retriever import retrieve_context
from app.services.email_generator import generate_email, generate_html_email


@pytest.fixture(autouse=True)
def ensure_mock_mode():
    """Ensure all integrations use mock mode without external API side-effects."""
    orig_gh = settings.GITHUB_MODE
    orig_email = settings.EMAIL_MODE

    settings.GITHUB_MODE = "mock"
    settings.EMAIL_MODE = "mock"

    yield

    settings.GITHUB_MODE = orig_gh
    settings.EMAIL_MODE = orig_email


def _cleanup_session(session_id: str):
    db = SessionLocal()
    try:
        db.query(models.ChecklistItemDB).filter(models.ChecklistItemDB.session_id == session_id).delete()
        db.query(models.OnboardingSessionDB).filter(models.OnboardingSessionDB.session_id == session_id).delete()
        db.query(models.ChatMessageDB).filter(models.ChatMessageDB.session_id == session_id).delete()
        db.commit()
    finally:
        db.close()


# ============================================================================
# Canonical Persona 1: Backend Intern — Node.js
# ============================================================================

def test_e2e_backend_intern_nodejs_onboarding():
    """
    Full end-to-end lifecycle verification for Backend Intern (Node.js/TypeScript).
    """
    session_id = "e2e-session-backend-intern"
    _cleanup_session(session_id)

    db = SessionLocal()
    try:
        # Create session record
        session_row = models.OnboardingSessionDB(
            session_id=session_id,
            employee_email="riya.sharma@novabyte.io",
            persona_match="Unknown",
            status="In Progress",
            current_phase="greeting",
        )
        db.add(session_row)
        db.commit()

        # Step 1: Persona Identification & Plan Generation
        intro_state = {
            "messages": [HumanMessage(content="Hi! I am Riya Sharma, joining as a Backend Intern working with Node.js and TypeScript.")],
            "session_id": session_id,
            "phase": "greeting",
            "onboarding_complete": False,
        }
        res_intro = invoke_agent(intro_state)

        # Verify Persona Identification
        assert res_intro.get("role", "").lower() == "backend"
        assert res_intro.get("experience_level", "").lower() == "intern"
        assert "node" in str(res_intro.get("technology_stack", [])).lower()
        assert res_intro.get("phase") in ("onboarding", "first_task")

        # Verify Personalized Onboarding Plan
        plan = res_intro.get("onboarding_plan", [])
        assert len(plan) > 0
        task_ids = [t["task_id"] for t in plan]
        task_titles = [t["title"].lower() for t in plan]
        assert any("node" in title or "api" in title or "backend" in title or "environment" in title for title in task_titles)
        assert task_ids[0] == "BI-01"

        # Verify Checklist Persistence in Database
        items = db.query(models.ChecklistItemDB).filter(models.ChecklistItemDB.session_id == session_id).all()
        assert len(items) == len(plan)
        assert any(i.id.endswith("BI-01") for i in items)

        # Step 2: Relevant RAG Retrieval for Backend/Node
        node_query = "What is the API design standard and error handling pattern for our Node.js services?"
        rag_res = retrieve_context(node_query, k=3, persona={"role": "backend", "technology_stack": ["node.js"]})
        assert len(rag_res["citations"]) > 0
        top_citation = rag_res["citations"][0]
        assert top_citation["role"] == "backend" or "node" in top_citation.get("technology", "").lower() or "node" in rag_res["context"].lower() or "api" in rag_res["context"].lower()

        # Step 3: Task Progression (Evidence-Aware Completion of Task 1)
        step1_state = {
            "messages": [HumanMessage(content="I have finished task BI-01: Node.js 20 is installed and npm run build succeeds.")],
            "session_id": session_id,
            "phase": "onboarding",
            "current_task_id": "BI-01",
            "onboarding_complete": False,
        }
        res_step1 = invoke_agent(step1_state)
        assert res_step1.get("updated_item_id") == "BI-01"
        assert res_step1.get("updated_item_status") == "Completed"
        assert res_step1.get("completed_count") == 1
        assert res_step1.get("current_task_id") == "BI-02"

        # Step 4: Starter Ticket / Tool Integration
        ticket_state = {
            "persona": {"role": "backend", "level": "intern", "stack": ["node.js"]},
            "phase": "first_task",
            "ticket_assigned": False,
        }
        from app.agent.nodes.ticket import run as ticket_run
        res_ticket = ticket_run(ticket_state)
        assert res_ticket.get("ticket_assigned") is True
        assert "GH-" in res_ticket.get("ticket_reference", "")

        # Step 5: Completion Detection & HR Summary Generation
        # Mark all tasks complete
        # Progress is evidence-aware, so seed completions the way the API records them.
        for itm in items:
            itm.status = "Completed"
            itm.completion_evidence = "Verified during test"
            itm.completion_source = "user_confirmation"
            itm.completed_at = datetime.now(timezone.utc)
        db.commit()

        final_task_id = task_ids[-1]
        completion_state = {
            "messages": [HumanMessage(content=f"I have finished the final task {final_task_id}. All onboarding tasks are complete.")],
            "session_id": session_id,
            "phase": "onboarding",
            "current_task_id": final_task_id,
            "onboarding_complete": False,
        }
        res_final = invoke_agent(completion_state)
        assert res_final.get("onboarding_complete") is True
        assert res_final.get("onboarding_status") == "completed"
        assert res_final.get("phase") == "completed"

        # Verify HR email report content
        email_data = {
            "name": "Riya Sharma",
            "email": "riya.sharma@novabyte.io",
            "role": "Backend Intern",
            "team": "Backend Core",
            "experience_level": "Intern",
            "tech_stack": ["Node.js", "TypeScript"],
            "total": len(items),
            "completed": len(items),
            "pending": 0,
            "ticket": "GH-backend-starter-101",
            "confidence_score": 100.0,
        }
        plain_email = generate_email(email_data)
        html_email = generate_html_email(email_data)
        assert "Riya Sharma" in plain_email
        assert "Backend Intern" in plain_email
        assert "Node.js, TypeScript" in html_email
        assert "100%" in html_email

    finally:
        _cleanup_session(session_id)
        db.close()


# ============================================================================
# Canonical Persona 2: Frontend Senior — React
# ============================================================================

def test_e2e_frontend_senior_react_onboarding():
    """
    Full end-to-end lifecycle verification for Frontend Senior (React/TypeScript/Vite).
    """
    session_id = "e2e-session-frontend-senior"
    _cleanup_session(session_id)

    db = SessionLocal()
    try:
        session_row = models.OnboardingSessionDB(
            session_id=session_id,
            employee_email="carlos.mendes@novabyte.io",
            persona_match="Unknown",
            status="In Progress",
            current_phase="greeting",
        )
        db.add(session_row)
        db.commit()

        # Step 1: Persona Identification & Plan Generation
        intro_state = {
            "messages": [HumanMessage(content="Hello! I'm Carlos Mendes, starting as a Senior Frontend Engineer focusing on React, TypeScript, and Vite.")],
            "session_id": session_id,
            "phase": "greeting",
            "onboarding_complete": False,
        }
        res_intro = invoke_agent(intro_state)

        # Verify Persona Identification
        assert res_intro.get("role", "").lower() == "frontend"
        assert res_intro.get("experience_level", "").lower() == "senior"
        assert "react" in str(res_intro.get("technology_stack", [])).lower()

        # Verify Senior Frontend Plan
        plan = res_intro.get("onboarding_plan", [])
        assert len(plan) > 0
        task_ids = [t["task_id"] for t in plan]
        task_titles = [t["title"].lower() for t in plan]
        assert task_ids[0] == "SFR-01"
        assert any("architecture" in title or "component" in title or "design system" in title or "frontend" in title for title in task_titles)

        # Verify Distinct Checklist from Backend Intern
        assert task_ids[0] != "BI-01"

        # Step 2: Relevant RAG Retrieval for Frontend/React
        react_query = "What is our component library standard and React state management pattern?"
        rag_res = retrieve_context(react_query, k=3, persona={"role": "frontend", "technology_stack": ["react"]})
        assert len(rag_res["citations"]) > 0
        top_citation = rag_res["citations"][0]
        assert top_citation["role"] == "frontend" or "react" in top_citation.get("technology", "").lower() or "react" in rag_res["context"].lower() or "frontend" in rag_res["context"].lower()

        # Step 3: Task Progression
        items = db.query(models.ChecklistItemDB).filter(models.ChecklistItemDB.session_id == session_id).all()
        step1_state = {
            "messages": [HumanMessage(content="I have reviewed the frontend architecture and confirmed task SFR-01 is complete.")],
            "session_id": session_id,
            "phase": "onboarding",
            "current_task_id": "SFR-01",
            "onboarding_complete": False,
        }
        res_step1 = invoke_agent(step1_state)
        assert res_step1.get("updated_item_id") == "SFR-01"
        assert res_step1.get("updated_item_status") == "Completed"
        assert res_step1.get("current_task_id") == "SFR-02"

        # Step 4: Starter Ticket / Tool Integration
        ticket_state = {
            "persona": {"role": "frontend", "level": "senior", "stack": ["react"]},
            "phase": "first_task",
            "ticket_assigned": False,
        }
        from app.agent.nodes.ticket import run as ticket_run
        res_ticket = ticket_run(ticket_state)
        assert res_ticket.get("ticket_assigned") is True
        assert any(k in res_ticket.get("ticket_reference", "") for k in ("ONBOARD-", "GH-"))

        # Step 5: Completion & HR Summary Generation
        # Progress is evidence-aware, so seed completions the way the API records them.
        for itm in items:
            itm.status = "Completed"
            itm.completion_evidence = "Verified during test"
            itm.completion_source = "user_confirmation"
            itm.completed_at = datetime.now(timezone.utc)
        db.commit()

        final_task_id = task_ids[-1]
        completion_state = {
            "messages": [HumanMessage(content=f"Completed {final_task_id}. Ready to finish.")],
            "session_id": session_id,
            "phase": "onboarding",
            "current_task_id": final_task_id,
            "onboarding_complete": False,
        }
        res_final = invoke_agent(completion_state)
        assert res_final.get("onboarding_complete") is True
        assert res_final.get("phase") == "completed"

        email_data = {
            "name": "Carlos Mendes",
            "email": "carlos.mendes@novabyte.io",
            "role": "Senior Frontend Engineer",
            "team": "UI & Design System",
            "experience_level": "Senior",
            "tech_stack": ["React", "TypeScript", "Vite"],
            "total": len(items),
            "completed": len(items),
            "pending": 0,
            "ticket": "GH-ONBOARD-101",
            "confidence_score": 100.0,
        }
        html_email = generate_html_email(email_data)
        assert "Carlos Mendes" in html_email
        assert "Senior Frontend Engineer" in html_email
        assert "Senior" in html_email
        assert "React, TypeScript, Vite" in html_email

    finally:
        _cleanup_session(session_id)
        db.close()


# ============================================================================
# Canonical Persona 3: DevOps Junior — Python/Docker
# ============================================================================

def test_e2e_devops_junior_docker_onboarding():
    """
    Full end-to-end lifecycle verification for DevOps Junior (Python/Docker/Kubernetes).
    """
    session_id = "e2e-session-devops-junior"
    _cleanup_session(session_id)

    db = SessionLocal()
    try:
        session_row = models.OnboardingSessionDB(
            session_id=session_id,
            employee_email="alex.chen@novabyte.io",
            persona_match="Unknown",
            status="In Progress",
            current_phase="greeting",
        )
        db.add(session_row)
        db.commit()

        # Step 1: Persona Identification & Plan Generation
        intro_state = {
            "messages": [HumanMessage(content="Hey team, I am Alex Chen, joining as a Junior DevOps Engineer working with Python, Docker, and Kubernetes.")],
            "session_id": session_id,
            "phase": "greeting",
            "onboarding_complete": False,
        }
        res_intro = invoke_agent(intro_state)

        # Verify Persona Identification
        assert res_intro.get("role", "").lower() == "devops"
        assert res_intro.get("experience_level", "").lower() == "junior"
        assert any(k in str(res_intro.get("technology_stack", [])).lower() for k in ["docker", "kubernetes", "python"])

        # Verify DevOps Junior Plan
        plan = res_intro.get("onboarding_plan", [])
        assert len(plan) > 0
        task_ids = [t["task_id"] for t in plan]
        task_titles = [t["title"].lower() for t in plan]
        assert task_ids[0] == "JDO-01"
        assert any("cloud" in title or "docker" in title or "container" in title or "infrastructure" in title for title in task_titles)

        # Verify Distinct from Backend & Frontend plans
        assert task_ids[0] not in ("BI-01", "SFR-01")

        # Step 2: Relevant RAG Retrieval for DevOps/Docker
        devops_query = "How do we configure Docker container environments and CI/CD pipelines?"
        rag_res = retrieve_context(devops_query, k=3, persona={"role": "devops", "technology_stack": ["docker", "kubernetes"]})
        assert len(rag_res["citations"]) > 0
        top_citation = rag_res["citations"][0]
        assert top_citation["role"] == "devops" or any(k in rag_res["context"].lower() for k in ["docker", "kubernetes", "ci/cd", "deployment", "aws", "terraform"])

        # Step 3: Task Progression
        items = db.query(models.ChecklistItemDB).filter(models.ChecklistItemDB.session_id == session_id).all()
        step1_state = {
            "messages": [HumanMessage(content="I have completed task JDO-01: Docker and VPN access is configured and verified.")],
            "session_id": session_id,
            "phase": "onboarding",
            "current_task_id": "JDO-01",
            "onboarding_complete": False,
        }
        res_step1 = invoke_agent(step1_state)
        assert res_step1.get("updated_item_id") == "JDO-01"
        assert res_step1.get("updated_item_status") == "Completed"
        assert res_step1.get("current_task_id") == "JDO-02"

        # Step 4: Starter Ticket / Tool Integration
        ticket_state = {
            "persona": {"role": "devops", "level": "junior", "stack": ["docker", "kubernetes"]},
            "phase": "first_task",
            "ticket_assigned": False,
        }
        from app.agent.nodes.ticket import run as ticket_run
        res_ticket = ticket_run(ticket_state)
        assert res_ticket.get("ticket_assigned") is True
        assert "GH-" in res_ticket.get("ticket_reference", "")

        # Step 5: Completion & HR Summary Generation
        # Progress is evidence-aware, so seed completions the way the API records them.
        for itm in items:
            itm.status = "Completed"
            itm.completion_evidence = "Verified during test"
            itm.completion_source = "user_confirmation"
            itm.completed_at = datetime.now(timezone.utc)
        db.commit()

        final_task_id = task_ids[-1]
        completion_state = {
            "messages": [HumanMessage(content=f"Task {final_task_id} is completed.")],
            "session_id": session_id,
            "phase": "onboarding",
            "current_task_id": final_task_id,
            "onboarding_complete": False,
        }
        res_final = invoke_agent(completion_state)
        assert res_final.get("onboarding_complete") is True
        assert res_final.get("phase") == "completed"

        email_data = {
            "name": "Alex Chen",
            "email": "alex.chen@novabyte.io",
            "role": "Junior DevOps Engineer",
            "team": "Infrastructure & Platform",
            "experience_level": "Junior",
            "tech_stack": ["Python", "Docker", "Kubernetes"],
            "total": len(items),
            "completed": len(items),
            "pending": 0,
            "ticket": "GH-infra-starter-101",
            "confidence_score": 100.0,
        }
        html_email = generate_html_email(email_data)
        assert "Alex Chen" in html_email
        assert "Junior DevOps Engineer" in html_email
        assert "Python, Docker, Kubernetes" in html_email

    finally:
        _cleanup_session(session_id)
        db.close()


# ============================================================================
# Persona Differentiation & Cross-Comparison
# ============================================================================

def test_cross_persona_differentiation_proof():
    """
    Explicit comparison proving that the 3 personas generate distinct onboarding paths,
    different task IDs, distinct categories, and tailored knowledge retrieval.
    """
    from app.services.plan_generator import generate_onboarding_plan

    plan_be = generate_onboarding_plan(role="backend", experience_level="intern", technology_stack=["node.js"])
    plan_fe = generate_onboarding_plan(role="frontend", experience_level="senior", technology_stack=["react"])
    plan_do = generate_onboarding_plan(role="devops", experience_level="junior", technology_stack=["docker", "python"])

    ids_be = {t.task_id for t in plan_be.tasks}
    ids_fe = {t.task_id for t in plan_fe.tasks}
    ids_do = {t.task_id for t in plan_do.tasks}

    # 1. No task ID collisions across the 3 plans
    assert len(ids_be.intersection(ids_fe)) == 0
    assert len(ids_be.intersection(ids_do)) == 0
    assert len(ids_fe.intersection(ids_do)) == 0

    # 2. Distinct titles reflecting role and seniority
    titles_be = " ".join([t.title for t in plan_be.tasks]).lower()
    titles_fe = " ".join([t.title for t in plan_fe.tasks]).lower()
    titles_do = " ".join([t.title for t in plan_do.tasks]).lower()

    assert "backend" in titles_be or "api" in titles_be or "node" in titles_be
    assert "frontend" in titles_fe or "component" in titles_fe or "ui" in titles_fe or "architecture" in titles_fe
    assert "docker" in titles_do or "cloud" in titles_do or "infrastructure" in titles_do

    # 3. Knowledge retrieval differentiation for identical prompt
    ambiguous_q = "What are the core technical standards and tools I should use?"
    rag_be = retrieve_context(ambiguous_q, k=2, persona={"role": "backend", "technology_stack": ["node.js"]})
    rag_fe = retrieve_context(ambiguous_q, k=2, persona={"role": "frontend", "technology_stack": ["react"]})
    rag_do = retrieve_context(ambiguous_q, k=2, persona={"role": "devops", "technology_stack": ["docker"]})

    assert rag_be["citations"][0]["role"] == "backend" or "node" in str(rag_be["citations"]).lower()
    assert rag_fe["citations"][0]["role"] == "frontend" or "react" in str(rag_fe["citations"]).lower()
    assert rag_do["citations"][0]["role"] == "devops" or any(k in str(rag_do["citations"]).lower() for k in ["docker", "kubernetes", "aws", "terraform"])
