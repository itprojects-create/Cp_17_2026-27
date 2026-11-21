import json

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.utils import get_current_user
from app.db.database import get_db
from app.db.models import UserDB, UserProfileDB
from app.services.profile_status import PROFILE_ROLES, is_profile_complete, missing_profile_fields

router = APIRouter(prefix="/profile", tags=["profile"])

PROFILE_OPTIONS = {
    "roles": PROFILE_ROLES,
    "languages": [
        "JavaScript", "TypeScript", "Python", "Go", "Rust", "Java", "C++", "C#", "Ruby", "PHP", "Swift", "Kotlin"
    ],
    "skills": [
        "React", "Vue", "Angular", "Node.js", "Express", "FastAPI", "Django", "Docker", "Kubernetes", "AWS", "GCP", "Azure",
        "PostgreSQL", "MongoDB", "Redis", "GraphQL", "REST API", "CI/CD", "Git", "Linux"
    ],
    "tools": [
        "VS Code", "WebStorm", "Vim", "Neovim", "Emacs", "Sublime Text", "IntelliJ", "PyCharm", "Figma", "Postman",
        "Docker Desktop", "iTerm2", "Windows Terminal"
    ],
    "timezones": [
        "UTC-12", "UTC-11", "UTC-10", "UTC-9", "UTC-8 (PST)", "UTC-7 (MST)", "UTC-6 (CST)", "UTC-5 (EST)",
        "UTC-4", "UTC-3", "UTC-2", "UTC-1", "UTC+0 (GMT)", "UTC+1 (CET)", "UTC+2", "UTC+3", "UTC+4", "UTC+5",
        "UTC+5:30 (IST)", "UTC+6", "UTC+7", "UTC+8", "UTC+9", "UTC+10", "UTC+11", "UTC+12"
    ],
}


DEFAULT_PROFILE = {
    "name": "",
    "email": "",
    "role": "",
    "skills": [],
    "programming_languages": [],
    "tech_stack": [],
    "years_of_experience": 0,
    "current_projects": "",
    "past_experience": "",
    "github_username": "",
    "preferred_tools": [],
    "timezone": "",
}


class ProfilePayload(BaseModel):
    name: str
    email: str
    role: str
    skills: list[str]
    programming_languages: list[str]
    tech_stack: list[str]
    years_of_experience: int
    current_projects: str
    past_experience: str
    github_username: str
    preferred_tools: list[str]
    timezone: str


def _read_profile(db: Session, user: UserDB) -> dict:
    row = db.query(UserProfileDB).filter(UserProfileDB.user_id == user.id).first()
    if not row:
        merged = DEFAULT_PROFILE.copy()
        merged["name"] = user.username
        merged["email"] = user.email
        return merged

    try:
        payload = json.loads(row.payload)
    except Exception:
        payload = {}

    merged = DEFAULT_PROFILE.copy()
    merged.update({k: v for k, v in payload.items() if k in merged})
    if not merged.get("name"):
        merged["name"] = user.username
    if not merged.get("email"):
        merged["email"] = user.email
    return merged


@router.get("")
def get_profile(
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    profile = _read_profile(db, current_user)
    return {**profile, "profile_completed": is_profile_complete(profile),
            "missing_fields": missing_profile_fields(profile)}


@router.get("/options")
def get_profile_options(
    current_user: UserDB = Depends(get_current_user),
):
    _ = current_user
    return PROFILE_OPTIONS


@router.put("")
def update_profile(
    payload: ProfilePayload,
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    import uuid
    from datetime import datetime, timezone
    from app.db import crud
    from app.services.persona_matcher import load_personas, match_persona, FALLBACK_PERSONA
    from app.services.plan_generator import apply_onboarding_plan

    row = db.query(UserProfileDB).filter(UserProfileDB.user_id == current_user.id).first()
    data = payload.model_dump()

    if not row:
        row = UserProfileDB(user_id=current_user.id, payload=json.dumps(data))
        db.add(row)
    else:
        row.payload = json.dumps(data)

    db.commit()

    # Determine matched persona from profile
    profile_dict = {
        "role": data.get("role"),
        "experience_level": "junior" if data.get("years_of_experience", 0) <= 2 else ("senior" if data.get("years_of_experience", 0) >= 5 else "mid"),
        "tech_stack": [t.lower() for t in (data.get("tech_stack", []) + data.get("programming_languages", []))],
    }
    matched = None
    try:
        personas = load_personas()
        matched = match_persona(profile_dict, personas)
        persona_name = matched.persona_key if matched else (data.get("role") or FALLBACK_PERSONA.persona_key)
    except Exception:
        persona_name = data.get("role") or "General Developer"

    # Synchronize with user's onboarding session
    session = (
        db.query(crud.models.OnboardingSessionDB)
        .filter(crud.models.OnboardingSessionDB.user_id == current_user.id)
        .order_by(crud.models.OnboardingSessionDB.started_at.desc())
        .first()
    )

    if not session:
        session_id = f"session_{uuid.uuid4().hex[:8]}"
        session = crud.models.OnboardingSessionDB(
            session_id=session_id,
            user_id=current_user.id,
            employee_email=current_user.email,
            persona_match=persona_name,
            status="In Progress",
            started_at=datetime.now(timezone.utc),
            current_phase="onboarding",
        )
        db.add(session)
        db.commit()

        # Seed initial greeting
        agent_msg_id = str(uuid.uuid4())
        crud.create_chat_message(
            db,
            agent_msg_id,
            session.session_id,
            "assistant",
            f"Welcome to NovaByte, {data.get('name') or current_user.username}! Your profile has been configured for {persona_name}. I have initialized your onboarding checklist and resources.",
        )
    else:
        if session.persona_match in ("Unknown", "", None) or data.get("role"):
            session.persona_match = persona_name
        if session.status != "Completed":
            session.status = "In Progress"
        db.commit()

    # The checklist is generated only from a complete profile. Re-planning replaces untouched
    # tasks from a previous plan and keeps anything already worked on.
    completed = is_profile_complete(data)
    if completed and session.status != "Completed":
        # Plan from what the user entered; the matched sample persona is only a label for retrieval.
        apply_onboarding_plan(
            db,
            session.session_id,
            role=data.get("role") or "general",
            experience_level=profile_dict["experience_level"],
            technology_stack=profile_dict["tech_stack"],
        )
        # The profile already supplied role and stack, so chat starts in onboarding instead of
        # asking for an introduction (which could re-plan from a less detailed chat message).
        if session.current_phase in (None, "", "greeting", "collect_info"):
            session.current_phase = "onboarding"
            db.commit()

    return {**data, "profile_completed": completed, "missing_fields": missing_profile_fields(data)}
