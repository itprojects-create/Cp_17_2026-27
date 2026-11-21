from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.auth.utils import get_password_hash
from app.config import settings
from app.db import models

DEMO_USERNAME = "demo_user"
DEMO_EMAIL = "demo@novabyte.dev"
DEMO_PASSWORD = "DemoPass123!"
DEMO_SESSION_ID = "demo-session"

DEMO_HR_USERNAME = "demo_hr"
DEMO_HR_EMAIL = "demo_hr@novabyte.dev"
DEMO_HR_PASSWORD = "DemoPass123!"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_user(db: Session) -> models.UserDB:
    user = (
        db.query(models.UserDB)
        .filter(
            (models.UserDB.username == DEMO_USERNAME)
            | (models.UserDB.email == DEMO_EMAIL)
        )
        .first()
    )
    if user:
        if not getattr(user, "role", None):
            user.role = "employee"
            db.commit()
        return user

    user = models.UserDB(
        username=DEMO_USERNAME,
        email=DEMO_EMAIL,
        password_hash=get_password_hash(DEMO_PASSWORD),
        role="employee",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _ensure_hr_user(db: Session) -> models.UserDB:
    user = (
        db.query(models.UserDB)
        .filter(
            (models.UserDB.username == DEMO_HR_USERNAME)
            | (models.UserDB.email == DEMO_HR_EMAIL)
        )
        .first()
    )
    if user:
        if getattr(user, "role", None) != "hr_admin":
            user.role = "hr_admin"
            db.commit()
        return user

    user = models.UserDB(
        username=DEMO_HR_USERNAME,
        email=DEMO_HR_EMAIL,
        password_hash=get_password_hash(DEMO_HR_PASSWORD),
        role="hr_admin",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user



def _ensure_settings(db: Session, user: models.UserDB) -> None:
    if db.query(models.UserSettingsDB).filter(models.UserSettingsDB.user_id == user.id).first():
        return

    db.add(
        models.UserSettingsDB(
            user_id=user.id,
            payload=json.dumps(
                {
                    "theme": "slate",
                    "notifications": True,
                    "email_digest": True,
                }
            ),
        )
    )


def _ensure_profile(db: Session, user: models.UserDB) -> None:
    if db.query(models.UserProfileDB).filter(models.UserProfileDB.user_id == user.id).first():
        return

    db.add(
        models.UserProfileDB(
            user_id=user.id,
            payload=json.dumps(
                {
                    "full_name": "Demo Developer",
                    "role": "backend",
                    "experience_level": "junior",
                    "tech_stack": ["python", "react", "typescript"],
                }
            ),
        )
    )


def _ensure_integrations(db: Session, user: models.UserDB, reference_time: datetime) -> None:
    integration_rows = {
        "github": "connected",
        "email": "connected",
    }

    for integration_name, status in integration_rows.items():
        row = (
            db.query(models.UserIntegrationDB)
            .filter(
                models.UserIntegrationDB.user_id == user.id,
                models.UserIntegrationDB.integration == integration_name,
            )
            .first()
        )
        if row:
            row.status = status
            row.last_sync = reference_time
            continue

        db.add(
            models.UserIntegrationDB(
                user_id=user.id,
                integration=integration_name,
                status=status,
                last_sync=reference_time,
            )
        )


def _ensure_session(db: Session, user: models.UserDB, started_at: datetime) -> models.OnboardingSessionDB:
    session = (
        db.query(models.OnboardingSessionDB)
        .filter(models.OnboardingSessionDB.session_id == DEMO_SESSION_ID)
        .first()
    )
    completed_at = started_at + timedelta(days=5, hours=4)

    if session:
        session.user_id = user.id
        session.employee_email = user.email
        session.persona_match = "Backend Junior Python"
        session.status = "Completed"
        session.started_at = started_at
        session.completed_at = completed_at
        session.current_phase = "completed"
        return session

    session = models.OnboardingSessionDB(
        session_id=DEMO_SESSION_ID,
        user_id=user.id,
        employee_email=user.email,
        persona_match="Backend Junior Python",
        status="Completed",
        started_at=started_at,
        completed_at=completed_at,
        current_phase="completed",
    )
    db.add(session)
    return session


def _ensure_checklist_items(db: Session, session: models.OnboardingSessionDB, started_at: datetime) -> None:
    checklist_rows = [
        ("ACC-01", "Create developer account", "Account Setup", "HR Team", "Day 1", 1),
        ("ACC-02", "Configure SSO and 2FA", "Account Setup", "Security", "Day 1", 1),
        ("DEV-01", "Set up local development environment", "Development", "Platform", "Day 1-2", 2),
        ("DEV-02", "Clone the starter repositories", "Development", "Engineering", "Day 2", 2),
        ("TEAM-01", "Meet your mentor and team", "Team Onboarding", "Manager", "Day 2-3", 3),
        ("DOC-01", "Review architecture and coding standards", "Architecture", "Engineering", "Day 3-4", 4),
        ("SHIP-01", "Complete your first starter task", "Delivery", "Engineering", "Day 5", 5),
        ("SHIP-02", "Submit your onboarding feedback", "Delivery", "HR Team", "Day 5", 5),
    ]

    existing_ids = {
        item.id
        for item in db.query(models.ChecklistItemDB).filter(
            models.ChecklistItemDB.session_id == session.session_id
        )
    }

    for item_id, task, category, owner, deadline, day_offset in checklist_rows:
        db_item_id = f"{session.session_id}::{item_id}"
        if db_item_id in existing_ids:
            continue

        completed_at = started_at + timedelta(days=day_offset, hours=day_offset)
        db.add(
            models.ChecklistItemDB(
                id=db_item_id,
                session_id=session.session_id,
                task=task,
                category=category,
                owner=owner,
                deadline=deadline,
                status="Completed",
                completed_at=completed_at,
            )
        )


def _ensure_chat_history(db: Session, session: models.OnboardingSessionDB, started_at: datetime) -> None:
    existing_messages = db.query(models.ChatMessageDB).filter(
        models.ChatMessageDB.session_id == session.session_id
    ).count()
    if existing_messages:
        return

    chat_rows = [
        ("assistant", "Welcome to NovaByte. I’ll guide you through setup and ramp-up.", 5),
        ("user", "I’m joining as a backend engineer focused on Python services.", 8),
        ("assistant", "Great. I’ve prepared your onboarding checklist and team access plan.", 12),
        ("user", "Please mark the dev environment and repository setup as done.", 24),
        ("assistant", "Done. Your onboarding checklist is updated and the next steps are ready.", 26),
    ]

    for index, (role, content, minute_offset) in enumerate(chat_rows, start=1):
        db.add(
            models.ChatMessageDB(
                id=f"{session.session_id}::msg::{index}",
                session_id=session.session_id,
                role=role,
                content=content,
                timestamp=started_at + timedelta(minutes=minute_offset),
            )
        )


def seed_demo_dashboard_data(db: Session, force: bool = False) -> bool:
    if not force and not settings.DEBUG:
        return False

    user = _ensure_user(db)
    hr_user = _ensure_hr_user(db)
    reference_time = _utcnow()
    started_at = reference_time - timedelta(days=6, hours=2)

    _ensure_settings(db, user)
    _ensure_profile(db, user)
    _ensure_integrations(db, user, reference_time)
    session = _ensure_session(db, user, started_at)
    _ensure_checklist_items(db, session, started_at)
    _ensure_chat_history(db, session, started_at)

    db.commit()
    return True