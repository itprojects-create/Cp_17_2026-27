from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import Optional
import re
from app.db import models

CHECKLIST_STATUSES = {
    "Not Started",
    "Pending",
    "In Progress",
    "Pending Verification",
    "Self-Reported Complete",
    "Completed",
    "Blocked",
    "Skipped",
}

CHECKLIST_TRANSITIONS = {
    "Not Started": {"Not Started", "In Progress", "Completed", "Blocked", "Skipped"},
    "Pending": {"Pending", "In Progress", "Completed", "Blocked", "Skipped"},
    "In Progress": {"In Progress", "Pending Verification", "Completed", "Blocked", "Skipped"},
    "Pending Verification": {"Pending Verification", "Completed", "In Progress", "Blocked"},
    "Self-Reported Complete": {"Self-Reported Complete", "Completed", "In Progress", "Blocked"},
    "Completed": {"Completed"},
    "Blocked": {"Blocked", "In Progress", "Skipped"},
    "Skipped": {"Skipped"},
}


def validate_checklist_transition(current_status: str, new_status: str) -> None:
    if new_status not in CHECKLIST_STATUSES:
        raise ValueError(f"Invalid status: {new_status}")
    if new_status not in CHECKLIST_TRANSITIONS.get(current_status, set()):
        raise ValueError(f"Invalid checklist transition: {current_status} -> {new_status}")


# Create onboarding session
def create_session(db: Session, session_id: str, email: str, persona: str):
    session = models.OnboardingSessionDB(
        session_id=session_id,
        employee_email=email,
        persona_match=persona,
        status="Not Started",
        started_at=datetime.now(timezone.utc),
        current_phase="greeting"
    )

    db.add(session)
    db.commit()
    db.refresh(session)

    return session


# Get session
def get_session(db: Session, session_id: str):
    return db.query(models.OnboardingSessionDB).filter(
        models.OnboardingSessionDB.session_id == session_id
    ).first()


# Create chat message
def create_chat_message(
    db: Session,
    message_id: str,
    session_id: str,
    role: str,
    content: str
):
    message = models.ChatMessageDB(
        id=message_id,
        session_id=session_id,
        role=role,
        content=content,
        timestamp=datetime.now(timezone.utc)
    )

    db.add(message)
    db.commit()
    db.refresh(message)

    return message


# Get messages for a session
def get_chat_messages(db, session_id):

    return (
        db.query(models.ChatMessageDB)
        .filter(models.ChatMessageDB.session_id == session_id)
        .order_by(models.ChatMessageDB.timestamp.asc())
        .all()
    )


# Create checklist item
def create_checklist_item(
    db: Session,
    item_id: str,
    session_id: str,
    task: str,
    category: str,
    owner: str,
    deadline: str,
    status: str = "Not Started",
    completion_evidence: Optional[str] = None,
    completed_at: Optional[datetime] = None,
    completion_source: Optional[str] = None,
):
    item = models.ChecklistItemDB(
        id=item_id,
        session_id=session_id,
        task=task,
        category=category,
        owner=owner,
        deadline=deadline,
        status=status,
        completion_evidence=completion_evidence,
        completed_at=completed_at,
        completion_source=completion_source,
    )

    db.add(item)
    db.commit()
    db.refresh(item)

    return item


# Update checklist status
def update_checklist_status(
    db: Session,
    item_id: str,
    status: str,
    session_id: str | None = None,
    completion_evidence: str | None = None,
    completion_source: str | None = None,
    completed_at: datetime | None = None,
):
    query = db.query(models.ChecklistItemDB)
    if session_id:
        query = query.filter(models.ChecklistItemDB.session_id == session_id)
        item = query.filter(
            (models.ChecklistItemDB.id == item_id)
            | (models.ChecklistItemDB.id == f"{session_id}::{item_id}")
        ).first()
    else:
        item = query.filter(models.ChecklistItemDB.id == item_id).first()

    if not item:
        return None

    validate_checklist_transition(item.status or "Not Started", status)
    if status == "Completed" and not (
        (completion_evidence and completion_evidence.strip())
        and (completion_source and completion_source.strip())
    ):
        raise ValueError(
            "Completed tasks require verification evidence and a completion source"
        )
    item.status = status

    if completion_evidence is not None:
        item.completion_evidence = completion_evidence

    if completion_source is not None:
        item.completion_source = completion_source

    if status == "Completed":
        item.completed_at = completed_at or datetime.now(timezone.utc)
        if not item.completion_source:
            item.completion_source = completion_source or "user_confirmation"
    elif status in ("Not Started", "In Progress", "Pending", "Pending Verification", "Self-Reported Complete"):
        if completed_at is None and completion_evidence is None:
            item.completed_at = None
            item.completion_evidence = None
            item.completion_source = None

    db.commit()
    db.refresh(item)

    return item


def get_session_ticket(db: Session, session_id: str) -> str:
    """Resolve the ticket text for a session from chat context, with file-based fallback."""
    messages = get_chat_messages(db, session_id)

    for message in reversed(messages):
        if message.role not in {"assistant", "tool"}:
            continue

        match = re.search(r"Starter ticket:\s*(.+)", message.content, flags=re.IGNORECASE)
        if match:
            ticket = match.group(1).strip()
            if ticket:
                return ticket

    # Keep fallback aligned with the ticket node source of truth.
    try:
        from app.agent.nodes.ticket import get_default_ticket_text

        return get_default_ticket_text()
    except Exception:
        return "Starter ticket assignment pending"