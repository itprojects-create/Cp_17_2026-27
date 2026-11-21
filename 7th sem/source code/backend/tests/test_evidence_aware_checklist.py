import pytest
import uuid
from datetime import datetime, timezone
from langchain_core.messages import HumanMessage

from app.db.database import SessionLocal
from app.db import crud, models
from app.agent.nodes.checklist import run as checklist_node
from app.agent.nodes.rag import run as rag_node
from app.agent.state import AgentState
from app.models.schemas import ChecklistItem, OnboardingTask
from app.agent.tools.checklist_tools import update_checklist_item


from app.db.init_db import init_db


@pytest.fixture
def db_session():
    init_db()
    db = SessionLocal()
    yield db
    db.close()


def test_user_confirmation_completion(db_session):
    """1. Test user confirmation marks task completed with evidence, timestamp, and user_confirmation source."""
    session_id = f"test-user-conf-{uuid.uuid4().hex[:8]}"
    item_id = f"{session_id}::DEV-01"

    crud.create_checklist_item(
        db=db_session,
        item_id=item_id,
        session_id=session_id,
        task="Environment Setup: Install Node.js 20 and Docker",
        category="Environment Setup",
        owner="Employee",
        deadline="Step 1",
        status="Pending",
    )

    state: AgentState = {
        "messages": [HumanMessage(content="I have finished DEV-01, installed Node.js 20 and Docker Desktop.")],
        "session_id": session_id,
        "current_task_id": "DEV-01",
        "phase": "onboarding",
    }

    result = checklist_node(state)

    assert result["updated_item_id"] == "DEV-01"
    assert result["updated_item_status"] == "Completed"
    assert result["completion_source"] == "user_confirmation"
    assert "installed Node.js" in result["completion_evidence"]

    # Verify DB persistence of evidence, source, and completed_at
    db_item = db_session.query(models.ChecklistItemDB).filter(models.ChecklistItemDB.id == item_id).first()
    assert db_item is not None
    assert db_item.status == "Completed"
    assert db_item.completion_source == "user_confirmation"
    assert db_item.completion_evidence is not None
    assert db_item.completed_at is not None

    # Validate Schema compatibility
    schema_item = ChecklistItem.model_validate(db_item)
    assert schema_item.status == "Completed"
    assert schema_item.completion_source == "user_confirmation"
    assert schema_item.completion_evidence == db_item.completion_evidence


def test_tool_verification_completion(db_session):
    """2. Test tool verification marks task completed with tool evidence and tool_verification source."""
    session_id = f"test-tool-verif-{uuid.uuid4().hex[:8]}"
    item_id = f"{session_id}::DEV-02"

    crud.create_checklist_item(
        db=db_session,
        item_id=item_id,
        session_id=session_id,
        task="Repository Access: Verify GitHub invite and clone repo",
        category="Repository Access",
        owner="Employee",
        deadline="Step 2",
        status="Pending",
    )

    # Tool executes objective check and updates item
    evidence_text = "Tool verification: GitHub API confirmed user @novabyte-intern accepted org invite."
    tool_output = update_checklist_item.invoke({
        "session_id": session_id,
        "item_id": "DEV-02",
        "new_status": "Completed",
        "completion_evidence": evidence_text,
        "completion_source": "tool_verification",
    })

    assert "Completed" in tool_output
    assert "tool_verification" in tool_output

    db_item = db_session.query(models.ChecklistItemDB).filter(models.ChecklistItemDB.id == item_id).first()
    assert db_item is not None
    assert db_item.status == "Completed"
    assert db_item.completion_source == "tool_verification"
    assert db_item.completion_evidence == evidence_text
    assert db_item.completed_at is not None


def test_system_verification_completion(db_session):
    """3. Test system automated verification marks task completed with system_verification source."""
    session_id = f"test-sys-verif-{uuid.uuid4().hex[:8]}"
    item_id = f"{session_id}::DEV-03"

    crud.create_checklist_item(
        db=db_session,
        item_id=item_id,
        session_id=session_id,
        task="System Verification: Automated GitHub repository access sync",
        category="Communication",
        owner="System",
        deadline="Step 3",
        status="Pending",
    )

    sys_evidence = "System webhook dispatch ID #99281 confirmed GitHub organization access for the new hire."
    updated = crud.update_checklist_status(
        db=db_session,
        item_id=item_id,
        status="Completed",
        session_id=session_id,
        completion_evidence=sys_evidence,
        completion_source="system_verification",
    )

    assert updated is not None
    assert updated.status == "Completed"
    assert updated.completion_source == "system_verification"
    assert updated.completion_evidence == sys_evidence
    assert updated.completed_at is not None


def test_admin_override_completion(db_session):
    """4. Test admin override marks task completed with admin justification and admin_override source."""
    session_id = f"test-admin-over-{uuid.uuid4().hex[:8]}"
    item_id = f"{session_id}::DEV-04"

    crud.create_checklist_item(
        db=db_session,
        item_id=item_id,
        session_id=session_id,
        task="Security Training: Complete corporate compliance module",
        category="Compliance",
        owner="Employee",
        deadline="Step 4",
        status="Pending",
    )

    admin_evidence = "HR Admin Override: Employee provided valid certificate from previous employer. Approved by hr_admin@novabyte.com."
    updated = crud.update_checklist_status(
        db=db_session,
        item_id=item_id,
        status="Completed",
        session_id=session_id,
        completion_evidence=admin_evidence,
        completion_source="admin_override",
    )

    assert updated is not None
    assert updated.status == "Completed"
    assert updated.completion_source == "admin_override"
    assert "hr_admin@novabyte.com" in updated.completion_evidence
    assert updated.completed_at is not None


def test_task_explanation_does_not_mark_completed(db_session):
    """5. Rule 1: The agent explaining a task or answering a question must NOT mark the task completed."""
    session_id = f"test-explain-rule1-{uuid.uuid4().hex[:8]}"
    item_id = f"{session_id}::DEV-01"

    crud.create_checklist_item(
        db=db_session,
        item_id=item_id,
        session_id=session_id,
        task="Environment Setup: Install Node.js 20 and Docker Desktop",
        category="Environment Setup",
        owner="Employee",
        deadline="Step 1",
        status="Pending",
    )

    # User asks for an explanation of DEV-01
    state: AgentState = {
        "messages": [HumanMessage(content="Can you explain what I need to do for task DEV-01 and how to install Docker?")],
        "session_id": session_id,
        "current_task_id": "DEV-01",
        "intent": "question",
        "phase": "onboarding",
        "sources": [],
        "retrieved_sources": [],
        "retrieved_documents": [],
        "context_docs": "",
    }

    # Running RAG node for knowledge explanation
    rag_state = rag_node(state)
    state.update(rag_state)

    # Verify task in DB remains Pending and NOT completed
    db_item = db_session.query(models.ChecklistItemDB).filter(models.ChecklistItemDB.id == item_id).first()
    assert db_item is not None
    assert db_item.status == "Pending"
    assert db_item.completed_at is None
    assert db_item.completion_source is None
    assert db_item.completion_evidence is None


def test_existing_statuses_compatibility(db_session):
    """6. Test that existing status values ('In Progress', 'Blocked', 'Skipped', 'Not Started') remain fully compatible."""
    session_id = f"test-compat-{uuid.uuid4().hex[:8]}"

    for idx, status_val in enumerate(["In Progress", "Blocked", "Skipped", "Not Started"]):
        item_id = f"{session_id}::TASK-0{idx+1}"
        item = crud.create_checklist_item(
            db=db_session,
            item_id=item_id,
            session_id=session_id,
            task=f"Test Task {idx+1}",
            category="General",
            owner="Employee",
            deadline=f"Step {idx+1}",
            status=status_val,
        )
        assert item.status == status_val

        # Status update check
        updated = crud.update_checklist_status(db_session, item_id, status_val, session_id=session_id)
        assert updated.status == status_val
